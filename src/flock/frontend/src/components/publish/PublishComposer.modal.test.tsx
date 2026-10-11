import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Toast from '../common/Toast';
import { useFilterStore } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import { useUIStore } from '../../store/uiStore';
import PublishComposer from './PublishComposer';

const api = vi.hoisted(() => ({
  fetchArtifactTypes: vi.fn(),
  fetchAgents: vi.fn(),
  publishArtifact: vi.fn(),
}));
vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  ...api,
}));

const imageDef = { type: 'object', properties: { url: { type: 'string' } }, 'x-flock-image': true };

// The ticket triage of the mockups
const types = [
  {
    name: 'app.SupportTicket',
    schema: {
      type: 'object',
      description: 'A customer support ticket that needs routing.',
      properties: {
        subject: { type: 'string' },
        message: { type: 'string', description: "The customer's issue or question" },
        priority: { type: 'integer', default: 1 },
      },
      required: ['subject', 'message'],
    },
  },
  { name: 'app.TeamReply', schema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] } },
  { name: 'app.Page', schema: { type: 'object', properties: { ticket_id: { type: 'string' } } } },
  {
    name: 'app.Photo',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: { caption: { type: 'string' }, picture: { $ref: '#/$defs/Image' } },
      required: ['caption', 'picture'],
    },
  },
  { name: 'Decision[app.Route]', schema: { type: 'object', properties: { choice: { type: 'string' } } } },
  { name: 'flock.models.system_artifacts.WorkflowError', schema: { type: 'object', properties: { error: { type: 'string' } } } },
  { name: 'flock.decisions.explain.Explanation', schema: { type: 'object', properties: { text: { type: 'string' } } } },
];

const agent = (name: string, subscriptions: string[], output_types: string[], status = 'ready') => ({
  name,
  description: '',
  status,
  subscriptions,
  output_types,
});

const agents = [
  agent('triage', ['app.SupportTicket'], ['Decision[app.Route]'], 'running'),
  agent('urgency', ['app.SupportTicket'], ['Decision[app.Urgent]']),
  agent('billing_team', ['Decision[app.Route]'], ['app.TeamReply']),
  agent('supervisor', ['Decision[app.Route]'], ['app.TeamReply']),
  agent('pager', ['Decision[app.Route]', 'Decision[app.Urgent]'], ['app.Page']),
  agent('crm_sync', ['app.TeamReply'], ['app.CrmRecord']),
  agent('archive', ['app.CrmRecord'], []),
];

/** The composer as the dashboard shows it: while `showControls` is on, with the toast */
const Harness = () => {
  const show = useSettingsStore((state) => state.ui.showControls);
  return (
    <>
      {show && <PublishComposer />}
      <Toast />
    </>
  );
};

// An option reads "SupportTicket, 3 fields", a decision "Decision[Route]"
const option = (name: string) =>
  screen.getByRole('option', { name: new RegExp(`^${name.replace(/[[\]]/g, '\\$&')}(,|$)`) });

async function open() {
  render(<Harness />);
  await screen.findByRole('option', { name: /^SupportTicket,/ });
}

async function pickTicket() {
  await open();
  fireEvent.click(option('SupportTicket'));
  fireEvent.change(screen.getByLabelText(/^subject/), { target: { value: 'Double charge' } });
  fireEvent.change(screen.getByLabelText(/^message/), { target: { value: 'Refund one payment' } });
}

const jsonEditor = () => screen.getByLabelText('SupportTicket as JSON') as HTMLTextAreaElement;

describe('PublishComposer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchArtifactTypes.mockResolvedValue(types);
    api.fetchAgents.mockResolvedValue(agents);
    api.publishArtifact.mockResolvedValue({ status: 'success', correlation_id: '4e7b91c0-aaaa', message: '' });
    useSettingsStore.getState().setShowControls(true);
    useFilterStore.setState({ correlationId: null });
    useUIStore.setState({ toast: null });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('the modal', () => {
    it('is a modal dialog that takes the focus to the type search', async () => {
      await open();

      const dialog = screen.getByRole('dialog', { name: 'Publish to the blackboard' });
      expect(dialog).toHaveAttribute('aria-modal', 'true');
      expect(dialog).toHaveAccessibleDescription('Agents subscribed to the type pick it up right away');
      expect(screen.getByRole('textbox', { name: 'Find a type' })).toHaveFocus();
    });

    it('closes on a click on the scrim, the close button or Cancel', async () => {
      await open();
      fireEvent.click(screen.getByTestId('publish-scrim'));
      expect(useSettingsStore.getState().ui.showControls).toBe(false);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

      act(() => useSettingsStore.getState().setShowControls(true));
      fireEvent.click(await screen.findByRole('button', { name: 'Close' }));
      expect(useSettingsStore.getState().ui.showControls).toBe(false);

      act(() => useSettingsStore.getState().setShowControls(true));
      fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
      expect(useSettingsStore.getState().ui.showControls).toBe(false);
    });

    it('a click inside the dialog does not close it', async () => {
      await open();
      fireEvent.click(screen.getByRole('dialog'));
      expect(useSettingsStore.getState().ui.showControls).toBe(true);
    });

    it('keeps Tab inside', async () => {
      await open();
      const close = screen.getByRole('button', { name: 'Close' });
      const publish = screen.getByRole('button', { name: /^publish$/i });

      publish.focus();
      fireEvent.keyDown(publish, { key: 'Tab' });
      expect(close).toHaveFocus();

      fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
      expect(publish).toHaveFocus();
    });
  });

  describe('the type list', () => {
    it('groups the types, with the system types collapsed', async () => {
      await open();

      const list = screen.getByRole('listbox', { name: 'Artifact types' });
      const yours = within(list).getByRole('group', { name: 'Your types' });
      expect(within(yours).getAllByRole('option').map((o) => o.getAttribute('aria-label'))).toEqual([
        'SupportTicket, 3 fields',
        'TeamReply, 1 field',
        'Page, 1 field',
        'Photo, 2 fields',
      ]);
      const decisions = within(list).getByRole('group', { name: 'Decisions' });
      // A decision shows no field count, as in the mockup
      expect(within(decisions).getByRole('option')).toHaveTextContent(/^◆Decision\[Route\]$/);
      expect(within(decisions).getByRole('option')).toHaveAccessibleName('Decision[Route]');

      const toggle = screen.getByRole('button', { name: /system types/i });
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      expect(toggle).toHaveTextContent('2');
      expect(screen.queryByRole('option', { name: /^WorkflowError/ })).not.toBeInTheDocument();

      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-expanded', 'true');
      const system = screen.getByRole('listbox', { name: 'System types' });
      expect(within(system).getAllByRole('option').map((o) => o.getAttribute('title'))).toEqual([
        'flock.models.system_artifacts.WorkflowError',
        'flock.decisions.explain.Explanation',
      ]);
    });

    it('finds types by name and opens the system types it finds', async () => {
      await open();
      const search = screen.getByRole('textbox', { name: 'Find a type' });

      fireEvent.change(search, { target: { value: 'REPLY' } });
      expect(screen.getAllByRole('option').map((o) => o.getAttribute('title'))).toEqual(['app.TeamReply']);
      expect(screen.queryByRole('group', { name: 'Decisions' })).not.toBeInTheDocument();

      fireEvent.change(search, { target: { value: 'error' } });
      expect(screen.getAllByRole('option').map((o) => o.getAttribute('title'))).toEqual([
        'flock.models.system_artifacts.WorkflowError',
      ]);
      expect(screen.getByRole('button', { name: /system types/i })).toHaveAttribute('aria-expanded', 'true');

      fireEvent.change(search, { target: { value: 'nothing like it' } });
      expect(screen.queryAllByRole('option')).toEqual([]);
      expect(screen.getByText('No type matches.')).toBeInTheDocument();
    });

    it('moves through the types with the arrow keys and picks them', async () => {
      await open();
      const search = screen.getByRole('textbox', { name: 'Find a type' });

      fireEvent.keyDown(search, { key: 'ArrowDown' });
      expect(option('SupportTicket')).toHaveFocus();
      expect(option('SupportTicket')).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByLabelText(/^subject/)).toBeInTheDocument();

      fireEvent.keyDown(option('SupportTicket'), { key: 'ArrowDown' });
      expect(option('TeamReply')).toHaveFocus();
      expect(option('TeamReply')).toHaveAttribute('aria-selected', 'true');
      expect(option('SupportTicket')).toHaveAttribute('aria-selected', 'false');
      expect(option('TeamReply')).toHaveAttribute('tabindex', '0');
      expect(option('SupportTicket')).toHaveAttribute('tabindex', '-1');

      fireEvent.keyDown(option('TeamReply'), { key: 'End' });
      expect(option('Decision[Route]')).toHaveFocus();

      // On into the system types once they are open
      fireEvent.click(screen.getByRole('button', { name: /system types/i }));
      fireEvent.keyDown(option('Decision[Route]'), { key: 'ArrowDown' });
      expect(option('WorkflowError')).toHaveFocus();

      fireEvent.keyDown(option('WorkflowError'), { key: 'Home' });
      expect(option('SupportTicket')).toHaveFocus();
      fireEvent.keyDown(option('SupportTicket'), { key: 'ArrowUp' });
      expect(search).toHaveFocus();
    });
  });

  describe('the form', () => {
    it('shows the type, its description and its fields as in the mockup', async () => {
      await open();
      fireEvent.click(option('SupportTicket'));

      expect(screen.getByText('A customer support ticket that needs routing.')).toBeInTheDocument();
      expect(screen.getByLabelText('subject str · required')).toBeInTheDocument();
      expect(screen.getByLabelText("message str · The customer's issue or question")).toBeInTheDocument();
      expect(screen.getByLabelText('priority int')).toHaveValue(1);
      expect(screen.getByRole('button', { name: 'Form' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('switches to JSON and back, keeping the values', async () => {
      await pickTicket();

      fireEvent.click(screen.getByRole('button', { name: 'JSON' }));
      expect(screen.getByRole('button', { name: 'JSON' })).toHaveAttribute('aria-pressed', 'true');
      expect(JSON.parse(jsonEditor().value)).toEqual({ subject: 'Double charge', message: 'Refund one payment', priority: 1 });
      expect(jsonEditor().value).toBe(
        JSON.stringify({ subject: 'Double charge', message: 'Refund one payment', priority: 1 }, null, 2)
      );

      fireEvent.change(jsonEditor(), {
        target: { value: '{ "subject": "Charged twice", "message": "Refund one payment", "priority": 3 }' },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Form' }));

      expect(screen.getByLabelText(/^subject/)).toHaveValue('Charged twice');
      expect(screen.getByLabelText(/^priority/)).toHaveValue(3);
    });

    it('turns pictures in the JSON into picked images', async () => {
      await open();
      fireEvent.click(option('Photo'));
      fireEvent.click(screen.getByRole('button', { name: 'JSON' }));

      fireEvent.change(screen.getByLabelText('Photo as JSON'), {
        target: { value: '{ "caption": "red", "picture": { "url": "data:image/png;base64,UkVE" } }' },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Form' }));

      expect(screen.getByAltText('picture')).toHaveAttribute('src', 'data:image/png;base64,UkVE');
      expect(screen.getByRole('button', { name: 'Remove picture' })).toBeInTheDocument();
    });

    it('stays in JSON mode while the JSON does not parse, and says why', async () => {
      await pickTicket();
      fireEvent.click(screen.getByRole('button', { name: 'JSON' }));

      fireEvent.change(jsonEditor(), { target: { value: '{ "subject": ' } });
      fireEvent.click(screen.getByRole('button', { name: 'Form' }));

      expect(screen.getByText(/^The JSON does not parse:/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'JSON' })).toHaveAttribute('aria-pressed', 'true');
      expect(jsonEditor()).toBeInTheDocument();

      fireEvent.change(jsonEditor(), { target: { value: '[1, 2]' } });
      fireEvent.click(screen.getByRole('button', { name: 'Form' }));
      expect(screen.getByText('The JSON must be an object to show it as a form')).toBeInTheDocument();
    });

    it('checks the JSON against the schema before publishing it', async () => {
      await pickTicket();
      fireEvent.click(screen.getByRole('button', { name: 'JSON' }));

      fireEvent.change(jsonEditor(), { target: { value: '{ "subject": 3, "priority": "high" }' } });
      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

      expect(await screen.findByText('subject must be a string')).toBeInTheDocument();
      expect(screen.getByText('message is required')).toBeInTheDocument();
      expect(screen.getByText('priority must be an integer')).toBeInTheDocument();
      expect(api.publishArtifact).not.toHaveBeenCalled();

      fireEvent.change(jsonEditor(), { target: { value: '{ "subject": "Hi", "message": "Help", "extra": true }' } });
      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

      await waitFor(() =>
        expect(api.publishArtifact).toHaveBeenCalledWith('app.SupportTicket', { subject: 'Hi', message: 'Help', extra: true })
      );
    });

    it('does not publish JSON that does not parse', async () => {
      await pickTicket();
      fireEvent.click(screen.getByRole('button', { name: 'JSON' }));

      fireEvent.change(jsonEditor(), { target: { value: 'subject: Hi' } });
      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

      expect(await screen.findByText(/^The JSON does not parse:/)).toBeInTheDocument();
      expect(api.publishArtifact).not.toHaveBeenCalled();
    });
  });

  describe('Picked up by', () => {
    it('lists the subscribers with what they decide, and who runs after them', async () => {
      await open();
      fireEvent.click(option('SupportTicket'));

      const picked = await screen.findByRole('region', { name: 'Picked up by' });
      const chips = within(picked).getAllByRole('listitem');
      expect(chips.map((chip) => chip.textContent)).toEqual(['triage ◆ Route', 'urgency ◆ Urgent']);
      expect(within(chips[0]!).getByRole('img', { name: 'running' })).toHaveClass('sdot', 'run');
      expect(picked).toHaveTextContent(
        'and from there billing_team, supervisor or pager, depending on the decisions'
      );
    });

    it('says what the subscribers publish when no decision leads on', async () => {
      await open();
      fireEvent.click(option('TeamReply'));

      const picked = await screen.findByRole('region', { name: 'Picked up by' });
      expect(within(picked).getAllByRole('listitem').map((chip) => chip.textContent)).toEqual(['crm_sync CrmRecord']);
      expect(picked).toHaveTextContent('and from there archive, depending on what they publish');
    });

    it('says when no agent subscribes', async () => {
      await open();
      fireEvent.click(option('Page'));

      const picked = await screen.findByRole('region', { name: 'Picked up by' });
      expect(picked).toHaveTextContent('No agent subscribes to this type yet.');
      expect(within(picked).queryByRole('listitem')).not.toBeInTheDocument();
    });

    it('reads the agents once', async () => {
      await open();
      fireEvent.click(option('SupportTicket'));
      fireEvent.click(option('TeamReply'));

      expect(api.fetchAgents).toHaveBeenCalledTimes(1);
    });
  });

  describe('publishing', () => {
    it('publishes with Ctrl+Enter or ⌘+Enter from anywhere in the composer', async () => {
      await pickTicket();

      fireEvent.keyDown(screen.getByLabelText(/^message/), { key: 'Enter', ctrlKey: true });
      await waitFor(() => expect(api.publishArtifact).toHaveBeenCalledTimes(1));
      expect(api.publishArtifact).toHaveBeenCalledWith('app.SupportTicket', {
        subject: 'Double charge',
        message: 'Refund one payment',
        priority: 1,
      });

      act(() => useSettingsStore.getState().setShowControls(true));
      await pickTicketAgain();
      fireEvent.keyDown(option('SupportTicket'), { key: 'Enter', metaKey: true });
      await waitFor(() => expect(api.publishArtifact).toHaveBeenCalledTimes(2));
    });

    it('closes and shows a toast that follows the run, until Stop following', async () => {
      await pickTicket();
      expect(screen.getByLabelText('Follow this run on the board')).toBeChecked();

      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

      expect(await screen.findByText('Published SupportTicket · run 4e7b')).toHaveAttribute('title', '4e7b91c0-aaaa');
      expect(screen.getByText('Following run 4e7b')).toBeInTheDocument();
      expect(useFilterStore.getState().correlationId).toBe('4e7b91c0-aaaa');
      expect(useSettingsStore.getState().ui.showControls).toBe(false);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: 'Stop following' }));

      expect(useFilterStore.getState().correlationId).toBeNull();
      expect(screen.queryByText(/^Published SupportTicket/)).not.toBeInTheDocument();
    });

    it('Stop following leaves a correlation filter set since then alone', async () => {
      await pickTicket();
      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
      await screen.findByText('Following run 4e7b');

      act(() => useFilterStore.getState().setCorrelationId('another-run'));
      fireEvent.click(screen.getByRole('button', { name: 'Stop following' }));

      expect(useFilterStore.getState().correlationId).toBe('another-run');
    });

    it('a toast without following has no Stop following', async () => {
      await pickTicket();
      fireEvent.click(screen.getByLabelText('Follow this run on the board'));
      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

      expect(await screen.findByText('Published SupportTicket · run 4e7b')).toBeInTheDocument();
      expect(screen.queryByText(/^Following/)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Stop following' })).not.toBeInTheDocument();
      expect(useFilterStore.getState().correlationId).toBeNull();
    });

    it('keeps an error in the composer', async () => {
      api.publishArtifact.mockRejectedValueOnce(new Error('Type is not registered'));
      await pickTicket();

      fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

      expect(await screen.findByRole('alert')).toHaveTextContent('Type is not registered');
      expect(useSettingsStore.getState().ui.showControls).toBe(true);
      expect(useUIStore.getState().toast).toBeNull();
    });
  });
});

/** The composer opened again after publishing: the ticket picked and filled in */
async function pickTicketAgain() {
  fireEvent.click(await screen.findByRole('option', { name: /^SupportTicket,/ }));
  fireEvent.change(screen.getByLabelText(/^subject/), { target: { value: 'Again' } });
  fireEvent.change(screen.getByLabelText(/^message/), { target: { value: 'Still charged twice' } });
}
