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
