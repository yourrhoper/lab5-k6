// Учебный стенд: API формы подачи достижения по культурно-творческой деятельности
// (упрощённая копия бэкенда формы из ЛР1–ЛР4). Только для нагрузочного тестирования.
// Запуск: node server/server.js  (порт 3000, переменная PORT)

const http = require('http');
const crypto = require('crypto');
const { URL } = require('url');

const PORT = Number(process.env.PORT || 3000);
// Стоимость хэширования пароля (PBKDF2). Синхронный вызов — намеренно, как в «наивной» реализации.
const PBKDF2_ITER = Number(process.env.PBKDF2_ITER || 60000);
// HASH_MODE=sync  — исходная реализация (хэширование блокирует event loop)
// HASH_MODE=async — оптимизированная: хэширование в пуле потоков libuv
const HASH_MODE = process.env.HASH_MODE || 'sync';
const pbkdf2Async = require('util').promisify(crypto.pbkdf2);
const MAX_FILE = 10 * 1024 * 1024; // 10 МБ
const ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'pdf'];
const DICT = {
  eventLevels: ['Университетский', 'Городской', 'Региональный', 'Всероссийский', 'Международный'],
  achievementLevels: ['Победитель (1 место)', 'Призёр (2 место)', 'Призёр (3 место)', 'Лауреат', 'Дипломант', 'Участник'],
  participationTypes: ['Индивидуальное', 'Коллективное'],
};
// поля формы «Культурно-творческое достижение» (обязательные отмечены * на форме)
const REQUIRED = ['student', 'leader', 'eventLevel', 'achievementLevel', 'eventName', 'venue', 'performanceName'];
const OPTIONAL = ['eventDate', 'participationType', 'teamName'];

// ---- «база данных» в памяти ----
const SALT = 'sibsau-salt';
const users = new Map();
const DEFAULT_HASH = crypto.pbkdf2Sync('Passw0rd!', SALT, PBKDF2_ITER, 32, 'sha256').toString('hex');
for (let i = 1; i <= 500; i++) {
  const login = `student${i}`;
  users.set(login, {
    id: i,
    fio: `Студент ${i}`,
    hash: DEFAULT_HASH,
  });
}
const tokens = new Map();
const achievements = [];
let nextId = 1;
// предзаполнение ленты
for (let i = 0; i < 300; i++) {
  achievements.push({ id: nextId++, userId: 1 + (i % 500), eventLevel: DICT.eventLevels[i % 5], eventName: `Фестиваль «Студенческая весна» ${2020 + (i % 6)}`,
    performanceName: `Номер ${i}`, achievementLevel: DICT.achievementLevels[i % 6], venue: 'СибГУ им. М.Ф. Решетнёва', eventDate: '2026-04-15', status: 'Подтверждено', createdAt: Date.now() });
}

// имитация задержки ввода-вывода к БД (неблокирующая)
const db = (min = 3, max = 12) => new Promise((r) => setTimeout(r, min + Math.random() * (max - min)));

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(body) });
  res.end(body);
}

function readBody(req, limit = MAX_FILE + 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) { reject(Object.assign(new Error('too large'), { code: 413 })); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

// минимальный разбор multipart/form-data
function parseMultipart(buf, contentType) {
  const m = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType || '');
  if (!m) return null;
  const boundary = Buffer.from('--' + (m[1] || m[2]));
  const fields = {};
  let file = null;
  let pos = buf.indexOf(boundary);
  while (pos !== -1) {
    const start = pos + boundary.length + 2; // \r\n
    const next = buf.indexOf(boundary, start);
    if (next === -1) break;
    const part = buf.subarray(start, next - 2);
    const sep = part.indexOf('\r\n\r\n');
    if (sep !== -1) {
      const head = part.subarray(0, sep).toString('utf8');
      const data = part.subarray(sep + 4);
      const name = /name="([^"]*)"/i.exec(head);
      const filename = /filename="([^"]*)"/i.exec(head);
      if (filename) file = { name: filename[1], size: data.length, sha256: crypto.createHash('sha256').update(data).digest('hex') };
      else if (name) fields[name[1]] = data.toString('utf8');
    }
    pos = next;
  }
  return { fields, file };
}

function auth(req) {
  const h = req.headers['authorization'] || '';
  const t = h.startsWith('Bearer ') ? h.slice(7) : '';
  return tokens.get(t) || null;
}

async function handle(req, res) {
  const url = new URL(req.url, 'http://localhost');
  const p = url.pathname;

  if (req.method === 'GET' && p === '/api/health') return send(res, 200, { status: 'ok', uptime: process.uptime() });

  if (req.method === 'GET' && p === '/api/dictionaries') { await db(1, 4); return send(res, 200, DICT); }

  // список «Культурно-творческая деятельность» — достижения текущего студента
  if (req.method === 'GET' && p === '/api/achievements') {
    const u = auth(req);
    if (!u) return send(res, 401, { error: 'Требуется авторизация' });
    const page = Math.max(1, Number(url.searchParams.get('page') || 1));
    const limit = Math.min(50, Number(url.searchParams.get('limit') || 20));
    await db();
    const own = achievements.filter((a) => a.userId === u.id);
    const items = own.slice((page - 1) * limit, page * limit);
    return send(res, 200, { page, limit, total: achievements.length, items });
  }

  if (req.method === 'POST' && p === '/api/auth/login') {
    const body = JSON.parse((await readBody(req, 4096)).toString('utf8') || '{}');
    const u = users.get(body.login);
    await db();
    // узкое место: синхронное хэширование блокирует event loop
    const pwd = String(body.password || '');
    const hash = (HASH_MODE === 'async'
      ? await pbkdf2Async(pwd, SALT, PBKDF2_ITER, 32, 'sha256')
      : crypto.pbkdf2Sync(pwd, SALT, PBKDF2_ITER, 32, 'sha256')).toString('hex');
    if (!u || hash !== u.hash) return send(res, 401, { error: 'Неверный логин или пароль' });
    const token = crypto.randomBytes(24).toString('hex');
    tokens.set(token, u);
    return send(res, 200, { token, user: { id: u.id, fio: u.fio } });
  }

  if (req.method === 'POST' && p === '/api/achievements') {
    const u = auth(req);
    if (!u) return send(res, 401, { error: 'Требуется авторизация' });
    const mp = parseMultipart(await readBody(req), req.headers['content-type']);
    if (!mp) return send(res, 400, { error: 'Ожидается multipart/form-data' });
    const { fields, file } = mp;
    const errors = {};
    for (const f of REQUIRED) if (!fields[f] || !fields[f].trim()) errors[f] = 'Обязательное поле';
    if (fields.eventLevel && !DICT.eventLevels.includes(fields.eventLevel)) errors.eventLevel = 'Значение не из справочника';
    if (fields.achievementLevel && !DICT.achievementLevels.includes(fields.achievementLevel)) errors.achievementLevel = 'Значение не из справочника';
    if (!file) errors.file = 'Необходимо прикрепить подтверждающий документ';
    else {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!ALLOWED_EXT.includes(ext)) errors.file = 'Неподдерживаемый формат файла';
      else if (file.size > MAX_FILE) errors.file = 'Размер файла превышает 10 МБ';
    }
    if (Object.keys(errors).length) return send(res, 422, { errors });
    await db(8, 25); // запись в БД + сохранение файла
    const a = { id: nextId++, userId: u.id, file: file.name, status: 'Отправлено', createdAt: Date.now() };
    for (const f of [...REQUIRED, ...OPTIONAL]) a[f] = fields[f] || null;
    achievements.push(a);
    if (achievements.length > 5000) achievements.splice(0, achievements.length - 5000);
    return send(res, 201, { id: a.id, status: a.status });
  }

  const mm = /^\/api\/achievements\/(\d+)$/.exec(p);
  if (req.method === 'GET' && mm) {
    const u = auth(req);
    if (!u) return send(res, 401, { error: 'Требуется авторизация' });
    await db(2, 8);
    const a = achievements.find((x) => x.id === Number(mm[1]));
    if (!a) return send(res, 404, { error: 'Не найдено' });
    if (a.userId !== u.id) return send(res, 403, { error: 'Нет доступа' });
    return send(res, 200, a);
  }

  send(res, 404, { error: 'Not found' });
}

http.createServer((req, res) => {
  handle(req, res).catch((e) => send(res, e.code === 413 ? 413 : 500, { error: e.message }));
}).listen(PORT, () => console.log(`Стенд запущен: http://localhost:${PORT} (PBKDF2_ITER=${PBKDF2_ITER}, HASH_MODE=${HASH_MODE})`));
