import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AdvancedSettings from './AdvancedSettings';

const clearDashboardData = vi.hoisted(() => vi.fn());
vi.mock('../../utils/clearDashboardData', () => ({ clearDashboardData }));

describe('AdvancedSettings', () => {
  beforeEach(() => {
    clearDashboardData.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearDashboardData.mockReset();
  });

  it('clears the dashboard data after a confirmation', () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false })));
    vi.stubGlobal('confirm', () => true);
    render(<AdvancedSettings />);

    fireEvent.click(screen.getByRole('button', { name: 'Clear all dashboard data' }));

    expect(clearDashboardData).toHaveBeenCalledOnce();
  });

  it('asks to close other dashboard tabs when they hold the data', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false })));
    vi.stubGlobal('confirm', () => true);
    clearDashboardData.mockImplementation(async (_reload?: () => void, onBlocked?: () => void) => {
      onBlocked?.();
    });
    render(<AdvancedSettings />);

    fireEvent.click(screen.getByRole('button', { name: 'Clear all dashboard data' }));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Close the other dashboard tabs to finish clearing.',
    );
  });

  it('says when the data could not be cleared', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false })));
    vi.stubGlobal('confirm', () => true);
    clearDashboardData.mockRejectedValue(new Error('disk full'));
    render(<AdvancedSettings />);

    fireEvent.click(screen.getByRole('button', { name: 'Clear all dashboard data' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The dashboard data could not be cleared: disk full');
  });

  it('shows the dashboard version it was built as', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false })));
    const { version } = await import('../../../package.json');

    render(<AdvancedSettings />);

    expect(screen.getByText(version, { exact: false })).toBeTruthy();
  });

  it('keeps the data when the confirmation is declined', () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false })));
    vi.stubGlobal('confirm', () => false);
    render(<AdvancedSettings />);

    fireEvent.click(screen.getByRole('button', { name: 'Clear all dashboard data' }));

    expect(clearDashboardData).not.toHaveBeenCalled();
  });
});
