'use strict';

function enableDailyGames(root) {
  const games = [...root.querySelectorAll('.daily-game')];
  const position = root.querySelector('[data-game-position]');
  let current = 0;
  root.querySelectorAll('[data-game-step]').forEach(button => {
    button.disabled = games.length < 2;
    button.addEventListener('click', () => {
      if (games.length < 2) return;
      current = (current + Number(button.dataset.gameStep) + games.length) % games.length;
      games.forEach((game, index) => { game.hidden = index !== current; });
      position.textContent = `${current + 1} / ${games.length}`;
    });
  });
}

if (typeof document !== 'undefined') {
  document.querySelectorAll('.daily-games').forEach(enableDailyGames);
}
