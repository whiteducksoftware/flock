import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useUIStore } from '../../store/uiStore';
import Toast, { TOAST_MS } from './Toast';

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useUIStore.setState({ toast: null });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const show = (message: string, extra = {}) => act(() => useUIStore.getState().showToast({ message, ...extra }));

  it('shows the message in a live region, with its detail and tooltip', () => {
    render(<Toast />);
    const region = screen.getByRole('status');
    expect(region).toBeEmptyDOMElement();

    show('Published SupportTicket · run 4e7b', { title: '4e7b91c0', detail: 'Following run 4e7b' });

    expect(region).toHaveTextContent('Published SupportTicket · run 4e7b');
    expect(screen.getByText('Published SupportTicket · run 4e7b')).toHaveAttribute('title', '4e7b91c0');
    expect(screen.getByText('Following run 4e7b')).toBeInTheDocument();
  });

  it('closes itself after a while', () => {
    render(<Toast />);
    show('Published');

    act(() => vi.advanceTimersByTime(TOAST_MS - 1));
    expect(screen.getByText('Published')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByText('Published')).not.toBeInTheDocument();
    expect(useUIStore.getState().toast).toBeNull();
  });

  it('starts the clock again for a newer toast', () => {
    render(<Toast />);
    show('First');
    act(() => vi.advanceTimersByTime(TOAST_MS - 1000));

    show('Second');
    act(() => vi.advanceTimersByTime(TOAST_MS - 1));
    expect(screen.getByText('Second')).toBeInTheDocument();
  });

  it('closes with its close button', () => {
    render(<Toast />);
    show('Published');

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    expect(screen.queryByText('Published')).not.toBeInTheDocument();
  });

  it('runs its action and closes', () => {
    const onClick = vi.fn();
    render(<Toast />);
    show('Published', { action: { label: 'Stop following', onClick } });

    fireEvent.click(screen.getByRole('button', { name: 'Stop following' }));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Published')).not.toBeInTheDocument();
  });
});
