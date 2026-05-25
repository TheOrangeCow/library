let cardBackSVG = null;
let previousCardBackURL = null;

function tintCardBackSVG(svgText, theme) {
  if (theme === 'gold') return svgText;
  
  const hueShifts = {
    blue:   { hue: 210, satMul: 1.2 },
    green:  { hue: 120, satMul: 1.1 },
    red:    { hue: 0,   satMul: 1.2 },
    rose:   { hue: 330, satMul: 1.1 },
    violet: { hue: 270, satMul: 1.2 },
    silver: { hue: 220, satMul: 0.1 },
  };
  
  const config = hueShifts[theme];
  if (!config) return svgText;

  return svgText.replace(/#[0-9A-Fa-f]{6}/g, (hex) => {
    const r = parseInt(hex.slice(1,3), 16) / 255;
    const g = parseInt(hex.slice(3,5), 16) / 255;
    const b = parseInt(hex.slice(5,7), 16) / 255;
    
    const max = Math.max(r,g,b), min = Math.min(r,g,b);
    const l = (max + min) / 2;
    const d = max - min;
    const s = d === 0 ? 0 : d / (1 - Math.abs(2*l - 1));
    
    const newH = config.hue;
    const newS = Math.min(1, s * config.satMul);
    const newL = l;
    
    const c = (1 - Math.abs(2*newL - 1)) * newS;
    const x = c * (1 - Math.abs((newH / 60) % 2 - 1));
    const m = newL - c/2;
    let r2, g2, b2;
    if      (newH < 60)  { r2=c; g2=x; b2=0; }
    else if (newH < 120) { r2=x; g2=c; b2=0; }
    else if (newH < 180) { r2=0; g2=c; b2=x; }
    else if (newH < 240) { r2=0; g2=x; b2=c; }
    else if (newH < 300) { r2=x; g2=0; b2=c; }
    else                 { r2=c; g2=0; b2=x; }
    
    const R = Math.round((r2+m)*255).toString(16).padStart(2,'0');
    const G = Math.round((g2+m)*255).toString(16).padStart(2,'0');
    const B = Math.round((b2+m)*255).toString(16).padStart(2,'0');
    return `#${R}${G}${B}`;
  });
}

function applyThemeToCardBack(theme) {
  if (!cardBackSVG) return;

  const tinted = tintCardBackSVG(cardBackSVG, theme);

  if (previousCardBackURL) {
    URL.revokeObjectURL(previousCardBackURL);
    previousCardBackURL = null;
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