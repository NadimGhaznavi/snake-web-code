'use strict';

function selectedRank(hash, count) {
  const match = /^#rank-([1-9][0-9]*)$/.exec(hash);
  const rank = match ? Number(match[1]) : 1;
  return rank <= count ? rank : 1;
}

function showRank(focus = false) {
  const boards = [...document.querySelectorAll('.ranked-run')];
  const rank = selectedRank(window.location.hash, boards.length);
  boards.forEach((board, index) => { board.hidden = index !== rank - 1; });
  if (focus && boards[rank - 1]) boards[rank - 1].focus({preventScroll: true});
}

if (typeof document !== 'undefined') {
  showRank();
  window.addEventListener('hashchange', () => showRank(true));
}
