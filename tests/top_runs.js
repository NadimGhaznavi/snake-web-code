// Run after top-100.js with gjs.
function assert(value) { if (!value) throw new Error('Assertion failed'); }
assert(selectedRank('', 100) === 1);
assert(selectedRank('#rank-100', 100) === 100);
for (const hash of ['#rank-0', '#rank-101', '#rank--1', '#rank-2junk', '#unknown']) {
  assert(selectedRank(hash, 100) === 1);
}
const boards = Array.from({length: 3}, () => ({hidden: false, focus() {this.focused = true;}}));
globalThis.document = {querySelectorAll() {return boards;}};
window.location = {hash: ''};
showRank();
assert(!boards[0].hidden && boards[1].hidden && boards[2].hidden);
window.location.hash = '#rank-3';
showRank(true);
assert(boards[0].hidden && boards[1].hidden && !boards[2].hidden && boards[2].focused);
window.location.hash = '#rank-1';
showRank(true);
assert(!boards[0].hidden && boards[2].hidden);
document.querySelectorAll = () => [];
showRank(true);
const buttons = [3, 2].map(rank => ({
  dataset: {rank: String(rank)}, disabled: true,
  addEventListener(name, callback) {this.click = callback;},
}));
document.querySelectorAll = () => buttons;
enableRankButtons();
assert(buttons.every(button => !button.disabled));
buttons[0].click();
assert(window.location.hash === '#rank-3');
buttons[1].click();
assert(window.location.hash === '#rank-2');
print('Top 100 navigation checks passed');
