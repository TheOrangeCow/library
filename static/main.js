let cardBackSVG = null;
fetch('/static/cards/back.svg').then(r => r.text()).then(t => { cardBackSVG = t; });

const CARD_BACK_THEMES = {
  gold: {
  },
  blue: {
    '#2E2303': '#00141e',
    '#2F2405': '#001828',
    '#1A1B19': '#0d1f2b',
    '#9D6E13': '#1a7a8a',
    '#AC7F21': '#2191a3',
    '#C8A84B': '#3ab8cc',
    '#E8B84B': '#5bc4d4',
    '#B08A30': '#2e8a99',
    '#483406': '#002030',
  },
  green: {
    '#2E2303': '#001408',
    '#2F2405': '#001a0e',
    '#1A1B19': '#0d1f14',
    '#9D6E13': '#1a7a4a',
    '#AC7F21': '#21a35e',
    '#C8A84B': '#3acc80',
    '#E8B84B': '#3dd68c',
    '#B08A30': '#1fa05e',
    '#483406': '#002010',
  },
  red: {
    '#2E2303': '#1e0000',
    '#2F2405': '#280000',
    '#1A1B19': '#1f0d0d',
    '#9D6E13': '#8a1a1a',
    '#AC7F21': '#a32121',
    '#C8A84B': '#cc3a3a',
    '#E8B84B': '#e85555',
    '#B08A30': '#b03030',
    '#483406': '#300000',
  },
  rose: {
    '#2E2303': '#1e0e00',
    '#2F2405': '#281400',
    '#1A1B19': '#1f150d',
    '#9D6E13': '#8a3a1a',
    '#AC7F21': '#a34821',
    '#C8A84B': '#cc6040',
    '#E8B84B': '#e8896e',
    '#B08A30': '#b05540',
    '#483406': '#301000',
  },
  violet: {
    '#2E2303': '#0e0018',
    '#2F2405': '#130020',
    '#1A1B19': '#150d1f',
    '#9D6E13': '#6a1a8a',
    '#AC7F21': '#7e21a3',
    '#C8A84B': '#a03acc',
    '#E8B84B': '#b87ee8',
    '#B08A30': '#7a4ab0',
    '#483406': '#1a0030',
  },
  silver: {
    '#2E2303': '#080a0e',
    '#2F2405': '#0c0f14',
    '#1A1B19': '#0d1018',
    '#9D6E13': '#606570',
    '#AC7F21': '#787e8a',
    '#C8A84B': '#9aa0aa',
    '#E8B84B': '#c8cdd6',
    '#B08A30': '#8a909a',
    '#483406': '#101318',
  },
};

function tintCardBackSVG(svgText, theme) {
  const map = CARD_BACK_THEMES[theme];
  if (!map) return svgText;
  
  let result = svgText;
  for (const [from, to] of Object.entries(map)) {
    const regex = new RegExp(from.replace('#', '#?'), 'gi');
    result = result.replaceAll(from.toUpperCase(), to)
                   .replaceAll(from.toLowerCase(), to)
                   .replaceAll(from, to);
  }
  return result;
}


function applyThemeToCardBack(theme) {
  if (!cardBackSVG) return;
  const tinted = tintCardBackSVG(cardBackSVG, theme);
  const blob = new Blob([tinted], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  document.documentElement.style.setProperty('--card-back', `url('${url}')`);
}


fetch('/static/cards/back.svg')
  .then(r => r.text())
  .then(svgText => {
    cardBackSVG = svgText;
    
    const theme = document.documentElement.getAttribute('data-theme') || 'gold';
    applyThemeToCardBack(theme);
  });