import { describe, expect, it } from 'vitest';
import { fromControl } from './nodeClick';

describe('fromControl', () => {
  const node = () => {
    const element = document.createElement('div');
    element.className = 'react-flow__node';
    element.innerHTML = `
      <div class="card">
        <span class="name">billing_team</span>
        <button type="button"><span class="label">TimeoutError · 12:00</span></button>
        <a href="#x">link</a>
      </div>`;
    document.body.appendChild(element);
    return element;
  };

  it('tells a click on a control inside a node from a click on the node', () => {
    const element = node();

    expect(fromControl(element.querySelector('.label'))).toBe(true);
    expect(fromControl(element.querySelector('a'))).toBe(true);
    expect(fromControl(element.querySelector('.name'))).toBe(false);
    expect(fromControl(element)).toBe(false);
    expect(fromControl(null)).toBe(false);
    element.remove();
  });
});
