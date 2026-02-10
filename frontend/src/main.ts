import './style.css'

const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('Root element #app not found')
}

app.innerHTML = `
  <div class="shell">
    <header class="shell__header">
      <div class="shell__master">
        <div class="shell__avatar">КС</div>
        <div class="shell__master-info">
          <div class="shell__master-name">Екатерина Савина</div>
          <div class="shell__master-subtitle">маникюр · Пушкино</div>
        </div>
      </div>
      <button class="shell__pill shell__pill--primary" type="button">
        Открыть запись
      </button>
    </header>

    <main class="shell__main">
      <section class="shell__card shell__hero">
        <h1 class="shell__title">Запись к мастеру без лишних сообщений</h1>
        <p class="shell__subtitle">
          Выберите услугу, время и подтвердите запись. Напоминания приходят за 24 ч и за 2 ч — в любое время суток.
        </p>
      </section>

      <section class="shell__tabs">
        <button class="shell__tab shell__tab--active" type="button">Записаться</button>
        <button class="shell__tab" type="button">Мои записи</button>
      </section>

      <section class="shell__layout">
        <section class="shell__card shell__section">
          <h2 class="shell__section-title">Услуга</h2>
          <p class="shell__section-caption">Выберите вид обработки и покрытия.</p>

          <div class="shell__service-group">
            <h3 class="shell__service-group-title">Основные виды обработки</h3>
            <div class="shell__services">
              <button class="service-card" type="button">
                <div class="service-card__name">Аппаратный маникюр</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
              <button class="service-card" type="button">
                <div class="service-card__name">Комбинированный маникюр</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
              <button class="service-card service-card--active" type="button">
                <div class="service-card__name">Классический обрезной маникюр</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
              <button class="service-card" type="button">
                <div class="service-card__name">Пилочный маникюр</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
            </div>
          </div>
          <div class="shell__service-group">
            <h3 class="shell__service-group-title">Основные виды покрытий</h3>
            <div class="shell__services">
              <button class="service-card" type="button">
                <div class="service-card__name">Покрытие гель-лаком</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
              <button class="service-card" type="button">
                <div class="service-card__name">Покрытие обычным лаком</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
              <button class="service-card" type="button">
                <div class="service-card__name">Укрепляющее (базовое) покрытие</div>
                <div class="service-card__meta"><span>— мин</span><span>— ₽</span></div>
              </button>
            </div>
          </div>
        </section>

        <section class="shell__card shell__section">
          <h2 class="shell__section-title">Дата и время</h2>
          <p class="shell__section-caption">Свободные окошки подтянем из расписания мастера.</p>

          <div class="shell__calendar-placeholder">
            <div class="shell__calendar-header">
              <span>Февраль 2026</span>
              <div class="shell__calendar-nav">
                <button type="button" aria-label="Предыдущая неделя">‹</button>
                <button type="button" aria-label="Следующая неделя">›</button>
              </div>
            </div>
            <div class="shell__slots-row">
              <button class="slot slot--busy" type="button">10:00</button>
              <button class="slot slot--active" type="button">11:30</button>
              <button class="slot" type="button">13:00</button>
              <button class="slot" type="button">15:30</button>
            </div>
            <p class="shell__hint">Позже мы подставим реальные слоты из API.</p>
          </div>
        </section>
      </section>

      <section class="shell__card shell__summary">
        <div>
          <div class="shell__summary-title">Классический обрезной маникюр</div>
          <div class="shell__summary-meta">9 февраля · 11:30 · — мин</div>
        </div>
        <button class="shell__pill shell__pill--primary" type="button">
          Подтвердить запись
        </button>
      </section>
    </main>
  </div>
`
