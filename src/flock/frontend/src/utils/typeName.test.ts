import { render, screen } from '@testing-library/react';
import { createElement } from 'react';
import { describe, expect, it } from 'vitest';
import TypeName from '../components/common/TypeName';
import { shortTypeName } from './typeName';

describe('shortTypeName', () => {
  it('drops the module path', () => {
    expect(shortTypeName('__main__.SupportTicket')).toBe('SupportTicket');
    expect(shortTypeName('flock.models.system_artifacts.WorkflowError')).toBe('WorkflowError');
    expect(shortTypeName('SupportTicket')).toBe('SupportTicket');
  });

  it('shortens the types inside a decision type', () => {
    expect(shortTypeName('Decision[__main__.Route]')).toBe('Decision[Route]');
    expect(shortTypeName('Coverage[app.checks.Controls]')).toBe('Coverage[Controls]');
  });
});

describe('TypeName', () => {
  it('shows the short name and keeps the full one in the tooltip', () => {
    render(createElement(TypeName, { name: '__main__.SupportTicket' }));

    const name = screen.getByText('SupportTicket');
    expect(name.getAttribute('title')).toBe('__main__.SupportTicket');
  });
});
