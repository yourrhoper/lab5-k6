// ЛР5. Нагрузочное тестирование API формы подачи достижения (k6)
// Запуск:  k6 run -e PROFILE=load   k6/achievements-test.js
//          k6 run -e PROFILE=stress k6/achievements-test.js
//          k6 run -e PROFILE=spike  k6/achievements-test.js
import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const PROFILE = __ENV.PROFILE || 'load';

// ---------- custom metrics ----------
const submitFlowDuration = new Trend('submit_flow_duration', true); // время всей бизнес-цепочки
const loginDuration = new Trend('login_duration', true);
const submitSuccess = new Rate('submit_success');                  // доля успешно отправленных заявлений
const achievementsCreated = new Counter('achievements_created');

// ---------- профили нагрузки (browse : submit = 3 : 2) ----------
// Целевая (рабочая) нагрузка: 50 VU = 30 browse + 20 submit
function stagesFor(share) {
  const v = (n) => Math.round(n * share);
  switch (PROFILE) {
    case 'stress': // ×1 → ×2 → ×3 → ×4 → ×5 от целевой нагрузки
      return [
        { duration: '1m', target: v(50) },  { duration: '1m30s', target: v(50) },
        { duration: '30s', target: v(100) }, { duration: '1m30s', target: v(100) },
        { duration: '30s', target: v(150) }, { duration: '1m30s', target: v(150) },
        { duration: '30s', target: v(200) }, { duration: '1m30s', target: v(200) },
        { duration: '30s', target: v(250) }, { duration: '1m30s', target: v(250) },
        { duration: '30s', target: 0 },
      ];
    case 'spike': // фон 10 VU → резкий скачок до 250 VU (×5) за 10 с → возврат
      return [
        { duration: '30s', target: v(10) },  { duration: '1m', target: v(10) },
        { duration: '10s', target: v(250) }, { duration: '1m', target: v(250) },
        { duration: '10s', target: v(10) },  { duration: '1m30s', target: v(10) },
        { duration: '10s', target: 0 },
      ];
    case 'smoke': // проверка работоспособности скрипта
      return [{ duration: '10s', target: v(5) }, { duration: '10s', target: v(5) }];
    default: // load: плавный рост до 50 VU, удержание 5 минут
      return [
        { duration: '1m', target: v(50) },
        { duration: '5m', target: v(50) },
        { duration: '30s', target: 0 },
      ];
  }
}

const stressLike = PROFILE === 'stress' || PROFILE === 'spike';

export const options = {
  scenarios: {
    browse: { executor: 'ramping-vus', exec: 'browse', startVUs: 0, stages: stagesFor(0.6), gracefulRampDown: '10s' },
    submit: { executor: 'ramping-vus', exec: 'submit', startVUs: 0, stages: stagesFor(0.4), gracefulRampDown: '10s' },
  },
  thresholds: {
    // SLA (см. раздел «Критерии приёмки» отчёта)
    'http_req_duration': ['p(95)<2000', 'p(99)<3000'],
    'http_req_duration{scenario:browse}': ['p(95)<500'],
    'http_req_duration{scenario:submit}': ['p(95)<2000'],
    'http_req_failed': stressLike
      ? ['rate<0.01', { threshold: 'rate<0.30', abortOnFail: true, delayAbortEval: '30s' }] // защитный стоп-кран
      : ['rate<0.01'],
    'checks': ['rate>0.99'],
    'submit_flow_duration': ['p(95)<3000'],
    'submit_success': ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

const REQ = { timeout: '10s' }; // как proxy_read_timeout у реального шлюза

// ---------- setup: заранее авторизованные студенты для «лёгкого» сценария ----------
export function setup() {
  const tokens = [];
  for (let i = 451; i <= 500; i++) {
    const r = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({ login: `student${i}`, password: 'Passw0rd!' }),
      { headers: { 'Content-Type': 'application/json' }, tags: { name: 'setup login' } });
    tokens.push(r.json('token'));
  }
  return { tokens };
}

// ---------- Сценарий 1: «лёгкий» — открытие раздела «Культурно-творческая деятельность» ----------
export function browse(data) {
  const auth = { Authorization: `Bearer ${data.tokens[__VU % data.tokens.length]}` };
  group('Открытие раздела «Культурно-творческая деятельность»', () => {
    const h = http.get(`${BASE_URL}/api/health`, { ...REQ, tags: { name: 'GET /api/health' } });
    check(h, { 'health: status 200': (r) => r.status === 200, 'health: status ok': (r) => r.json('status') === 'ok' });

    const list = http.get(`${BASE_URL}/api/achievements?page=1&limit=20`, { ...REQ, headers: auth, tags: { name: 'GET /api/achievements' } });
    check(list, {
      'list: status 200': (r) => r.status === 200,
      'list: есть items': (r) => Array.isArray(r.json('items')),
    });

    const dict = http.get(`${BASE_URL}/api/dictionaries`, { ...REQ, tags: { name: 'GET /api/dictionaries' } });
    check(dict, { 'dict: status 200': (r) => r.status === 200, 'dict: есть уровни мероприятия': (r) => (r.json('eventLevels') || []).length > 0 });
  });
  sleep(1);
}

// ---------- Сценарий 2: «бизнес» — вход → «Добавить» → заполнение → «Сохранить» → статус → список ----------
const pdf = new Uint8Array(200 * 1024).map((_, i) => (i * 31) % 256).buffer; // «документ» 200 КБ

export function submit() {
  const start = Date.now();
  let ok = false;
  group('Подача достижения', () => {
    const login = `student${1 + ((__VU * 7 + __ITER) % 450)}`;
    const lr = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({ login, password: 'Passw0rd!' }),
      { ...REQ, headers: { 'Content-Type': 'application/json' }, tags: { name: 'POST /api/auth/login' } });
    loginDuration.add(lr.timings.duration);
    if (!check(lr, { 'login: status 200': (r) => r.status === 200, 'login: есть token': (r) => !!r.json('token') })) return;
    const auth = { Authorization: `Bearer ${lr.json('token')}` };

    // кнопка «Добавить» — открытие формы, загрузка справочников для выпадающих списков
    const dict = http.get(`${BASE_URL}/api/dictionaries`, { ...REQ, tags: { name: 'GET /api/dictionaries' } });
    check(dict, { 'dict: status 200': (r) => r.status === 200 });

    sleep(1); // пользователь заполняет форму

    const form = {
      student: 'Иванов Иван Иванович', leader: 'Петрова Анна Андреевна',
      eventDate: '2026-04-15', eventLevel: 'Региональный', achievementLevel: 'Лауреат', participationType: 'Коллективное',
      eventName: 'Фестиваль «Студенческая весна»', venue: 'СибГУ им. М.Ф. Решетнёва',
      performanceName: 'Песня «Красноярск»', teamName: 'Народный хор',
      file: http.file(pdf, 'achievement.pdf', 'application/pdf'),
    };
    const sr = http.post(`${BASE_URL}/api/achievements`, form, { ...REQ, headers: auth, tags: { name: 'POST /api/achievements' } });
    const created = check(sr, {
      'submit: status 201': (r) => r.status === 201,
      'submit: статус «Отправлено»': (r) => r.json('status') === 'Отправлено',
    });
    if (!created) return;
    achievementsCreated.add(1);

    const gr = http.get(`${BASE_URL}/api/achievements/${sr.json('id')}`, { ...REQ, headers: auth, tags: { name: 'GET /api/achievements/:id' } });
    ok = check(gr, { 'status: 200 и «Отправлено»': (r) => r.status === 200 && r.json('status') === 'Отправлено' });

    // после «Сохранить» студент возвращается к списку достижений
    const list = http.get(`${BASE_URL}/api/achievements?page=1&limit=20`, { ...REQ, headers: auth, tags: { name: 'GET /api/achievements' } });
    ok = check(list, { 'list: новое заявление в списке': (r) => r.status === 200 && (r.json('items') || []).some((a) => a.id === sr.json('id')) }) && ok;
  });
  submitSuccess.add(ok);
  submitFlowDuration.add(Date.now() - start - 1000); // без «думания» пользователя
  sleep(1);
}
