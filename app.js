const periods = {
  '7D': { reach: '4.3M', engagement: '5.98%', creators: '109', content: '126', total: '4,329,118', change: '+8.1% vs prior period' },
  '30D': { reach: '18.6M', engagement: '6.42%', creators: '124', content: '487', total: '18,642,089', change: '+12.4% vs prior period' },
  '90D': { reach: '51.4M', engagement: '6.11%', creators: '153', content: '1,389', total: '51,384,771', change: '+15.7% vs prior period' },
  YTD: { reach: '172M', engagement: '5.86%', creators: '236', content: '3,884', total: '172,086,412', change: '+21.2% vs prior period' }
};

const values = { reach: document.querySelector('#reach-value'), engagement: document.querySelector('#engagement-value'), creators: document.querySelector('#creators-value'), content: document.querySelector('#content-value'), total: document.querySelector('#chart-total'), change: document.querySelector('#chart-change') };
const title = document.querySelector('#page-title');
const kicker = document.querySelector('#view-kicker');

document.querySelectorAll('.period-button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelector('.period-button.active').classList.remove('active');
    button.classList.add('active');
    const data = periods[button.dataset.period];
    Object.entries(values).forEach(([key, element]) => { element.textContent = data[key]; });
  });
});

document.querySelectorAll('.chart-mode').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelector('.chart-mode.active').classList.remove('active');
    button.classList.add('active');
    const engagement = button.dataset.mode === 'engagement';
    values.total.textContent = engagement ? values.engagement.textContent : periods[document.querySelector('.period-button.active').dataset.period].total;
    values.change.textContent = engagement ? 'Healthy quality signal across channels' : periods[document.querySelector('.period-button.active').dataset.period].change;
  });
});

document.querySelectorAll('.nav-item').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelector('.nav-item.active').classList.remove('active');
    button.classList.add('active');
    title.textContent = button.textContent.replace(/^\d+/, '').trim();
    kicker.textContent = `${button.querySelector('span').textContent} / ${button.textContent.replace(/^\d+/, '').trim().toUpperCase()}`;
  });
});

const toast = document.querySelector('#toast');
document.querySelector('#export-button').addEventListener('click', () => {
  toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 2600);
});