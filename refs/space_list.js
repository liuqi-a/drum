// 用途：在 B 站 UP 主空间页里抽取投稿列表（BV 号、标题、时长），返回 JSON 字符串
(() => {
  const rows = [];
  document.querySelectorAll('a[href*="/video/BV"]').forEach((a) => {
    const href = a.getAttribute('href') || '';
    const m = href.match(/BV[0-9A-Za-z]{10}/);
    if (!m) return;
    const card = a.closest('.bili-video-card') || a.closest('li') || a.parentElement;
    let title = (a.getAttribute('title') || '').trim();
    let dur = '';
    if (card) {
      if (!title) {
        const t = card.querySelector('.bili-video-card__info--tit, .title, p');
        if (t) title = (t.getAttribute('title') || t.textContent || '').trim();
      }
      const d = card.querySelector('.bili-video-card__stats__duration, .duration');
      if (d) dur = (d.textContent || '').trim();
    }
    rows.push({ bv: m[0], title: title, dur: dur });
  });
  const seen = new Set();
  const uniq = rows.filter((o) => (seen.has(o.bv) ? false : (seen.add(o.bv), true)));
  return JSON.stringify(uniq, null, 1);
})()
