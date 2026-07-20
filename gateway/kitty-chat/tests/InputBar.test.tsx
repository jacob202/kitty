import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { InputBar } from '../src/components/InputBar';

function setup(value: string, overrides?: Parameters<typeof InputBar>[0]) {
  const onChange = vi.fn();
  const onSend = vi.fn();
  render(
    <InputBar
      value={value}
      onChange={onChange}
      onSend={onSend}
      disabled={false}
      {...overrides}
    />,
  );
  const textarea = screen.getByPlaceholderText('ask kitty anything') as HTMLTextAreaElement;
  return { textarea, onChange, onSend };
}

describe('InputBar keyboard behaviour', () => {
  afterEach(cleanup);
  it('Enter on non-empty value dispatches onSend', () => {
    const { textarea, onSend } = setup('hello');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false, metaKey: false, ctrlKey: false });
    expect(onSend).toHaveBeenCalledOnce();
  });

  it('Shift+Enter does NOT send', () => {
    const { textarea, onSend } = setup('hello');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true, metaKey: false, ctrlKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('Enter on empty (whitespace-only) value does NOT send', () => {
    const { textarea, onSend } = setup('   ');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false, metaKey: false, ctrlKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('Enter when disabled does NOT send', () => {
    const { textarea, onSend } = setup('hello', { disabled: true });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false, metaKey: false, ctrlKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe('CR-07 per-message model override', () => {
  afterEach(cleanup)

  const models = [
    { id: 'claude-sonnet-4-6', name: 'sonnet-4', color: '#a884ff', glow: '#a884ff99' },
    { id: 'gpt-4o', name: 'gpt-4o', color: '#f4c542', glow: '#f4c54299' },
  ]

  it('selecting a model arms a one-shot override and shows the chip', () => {
    const onOverrideModel = vi.fn()
    render(
      <InputBar
        value=""
        onChange={() => {}}
        onSend={() => {}}
        models={models}
        overrideModel={null}
        onOverrideModel={onOverrideModel}
      />,
    )
    fireEvent.click(screen.getByLabelText('model override for next message'))
    fireEvent.click(screen.getByRole('menuitem', { name: /sonnet-4/ }))
    expect(onOverrideModel).toHaveBeenCalledWith(models[0])
  })

  it('shows the armed chip and clears it on ✕', () => {
    const onOverrideModel = vi.fn()
    render(
      <InputBar
        value=""
        onChange={() => {}}
        onSend={() => {}}
        models={models}
        overrideModel={models[1]}
        onOverrideModel={onOverrideModel}
      />,
    )
    expect(screen.getByText(/next message → gpt-4o/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('clear model override'))
    expect(onOverrideModel).toHaveBeenCalledWith(null)
  })

  it('renders no override affordance when the callback is absent', () => {
    render(<InputBar value="" onChange={() => {}} onSend={() => {}} models={models} />)
    expect(screen.queryByLabelText('model override for next message')).not.toBeInTheDocument()
  })
})
