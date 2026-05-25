let cardBackSVG = null;
fetch('/static/cards/back.svg').then(r => r.text()).then(t => { cardBackSVG = t; });

const CARD_BACK_THEMES = {
  gold: {}, // original SVG colors — perfect as-is

  blue: {
    '#2E2303': '#021420',
    '#2F2405': '#031a28',
    '#1A1B19': '#0a1520',
    '#9D6E13': '#0d5a7a',
    '#AC7F21': '#1a7a9a',
    '#C8A84B': '#2a9ab8',
    '#E8B84B': '#40b8d0',
    '#B08A30': '#1a7090',
    '#483406': '#01080f',
  },

  green: {
    '#2E2303': '#051a05',
    '#2F2405': '#072007',
    '#1A1B19': '#0a1a0a',
    '#9D6E13': '#2a7a1a',
    '#AC7F21': '#3a9a20',
    '#C8A84B': '#50b830',
    '#E8B84B': '#6ad040',
    '#B08A30': '#358a20',
    '#483406': '#020e02',
  },

  red: {
    '#2E2303': '#1a0303',
    '#2F2405': '#220505',
    '#1A1B19': '#1a0a0a',
    '#9D6E13': '#8a1a0d',
    '#AC7F21': '#aa2210',
    '#C8A84B': '#cc3318',
    '#E8B84B': '#e04520',
    '#B08A30': '#a02010',
    '#483406': '#0e0101',
  },

  rose: {
    '#2E2303': '#1a0810',
    '#2F2405': '#220a15',
    '#1A1B19': '#1a0d15',
    '#9D6E13': '#8a2a50',
    '#AC7F21': '#aa3868',
    '#C8A84B': '#cc5080',
    '#E8B84B': '#e06898',
    '#B08A30': '#a03060',
    '#483406': '#0e0208',
  },

  violet: {
    '#2E2303': '#0e0520',
    '#2F2405': '#130828',
    '#1A1B19': '#100a20',
    '#9D6E13': '#5a1a8a',
    '#AC7F21': '#7022aa',
    '#C8A84B': '#8a35cc',
    '#E8B84B': '#a050e0',
    '#B08A30': '#6020a0',
    '#483406': '#08010f',
  },

  silver: {
    '#2E2303': '#12141a',
    '#2F2405': '#181a20',
    '#1A1B19': '#141618',
    '#9D6E13': '#606570',
    '#AC7F21': '#787e8a',
    '#C8A84B': '#9aa0aa',
    '#E8B84B': '#c8cdd6',
    '#B08A30': '#8a909a',
    '#483406': '#0a0b0e',
  },
};

function tintCardBackSVG(svgText, theme) {
  const map = CARD_BACK_THEMES[theme];
  if (!map) return svgText;

  const entries = Object.entries(map).sort((a, b) => b[0].length - a[0].length);

  let result = svgText;
  for (const [from, to] of entries) {
    const escaped = from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(new RegExp(escaped, 'gi'), to);
  }
  return result;
}

let previousCardBackURL = null;

function applyThemeToCardBack(theme) {
  if (!cardBackSVG) return;

  const tinted = tintCardBackSVG(cardBackSVG, theme);

  if (previousCardBackURL) {
    URL.revokeObjectURL(previousCardBackURL);
  }

  const blob = new Blob([tinted], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  previousCardBackURL = url;

  document.documentElement.style.setProperty('--card-back', `url('${url}')`);
}


fetch('/static/cards/back.svg')
  .then(r => r.text())
  .then(svgText => {
    cardBackSVG = svgText;
    
    const theme = document.documentElement.getAttribute('data-theme') || 'gold';
    applyThemeToCardBack(theme);
  });