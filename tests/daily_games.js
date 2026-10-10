function assert(value) { if (!value) throw new Error('Assertion failed'); }
for (const count of [0, 1, 2, 3]) {
  const games = Array.from({length: count}, (_, i) => ({hidden: i !== 0}));
  const position = {textContent: count ? `1 / ${count}` : ''};
  const buttons = [-1, 1].map(step => ({
    dataset: {gameStep: String(step)}, disabled: true,
    addEventListener(name, callback) {this.click = callback;},
  }));
  const root = {
    querySelectorAll(selector) {return selector === '.daily-game' ? games : buttons;},
    querySelector() {return position;},
  };
  enableDailyGames(root);
  assert(buttons.every(button => button.disabled === (count < 2)));
  if (count < 2) {
    buttons[0].click();
    buttons[1].click();
    assert(position.textContent === (count ? '1 / 1' : ''));
  } else {
    buttons[0].click();
    assert(!games[count - 1].hidden && games[0].hidden);
    assert(position.textContent === `${count} / ${count}`);
    buttons[1].click();
    assert(!games[0].hidden && games[count - 1].hidden);
    for (let i = 0; i < count; i++) buttons[1].click();
    assert(!games[0].hidden);
  }
}
print('Daily game navigation checks passed');
