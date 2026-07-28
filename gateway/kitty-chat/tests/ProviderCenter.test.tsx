import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest';
import type { Mock } from 'vitest';
import {
  usePlugins, useTogglePlugin, useMcpServers, useMcpTools,
  useGatewayModels, useModelRouting, useProviders, useSaveProviders, useImageStatus,
} from '../src/lib/queries';
import { ProviderCenter } from '../src/components/ProviderCenter';

vi.mock('../src/lib/queries', () => ({
  usePlugins: vi.fn(), useTogglePlugin: vi.fn(), useMcpServers: vi.fn(),
  useMcpTools: vi.fn(), useGatewayModels: vi.fn(), useModelRouting: vi.fn(),
  useProviders: vi.fn(), useSaveProviders: vi.fn(), useImageStatus: vi.fn(),
}));

const EMPTY_QUERY = { data: undefined, isLoading: false, isError: false, isFetching: false, error: null, refetch: vi.fn() };

function provider(name: string, over = {}) {
  return {
    name, base_url: `https://${name}.example/v1`, model: `${name}-model`, model_env: null,
    api_key_env: [`${name.toUpperCase()}_API_KEY`], requires_key: true,
    configured: true, disabled: false, position: 0, ...over,
  };
}

let save: Mock;

beforeEach(() => {
  vi.clearAllMocks();
  save = vi.fn();
  (usePlugins as Mock).mockReturnValue({ ...EMPTY_QUERY, data: [] });
  (useTogglePlugin as Mock).mockReturnValue({ mutate: vi.fn(), isPending: false });
  (useMcpServers as Mock).mockReturnValue({ ...EMPTY_QUERY, data: [] });
  (useMcpTools as Mock).mockReturnValue({ ...EMPTY_QUERY, data: [] });
  (useGatewayModels as Mock).mockReturnValue({ ...EMPTY_QUERY, data: { models: [], fromLiveGateway: true, error: null } });
  (useModelRouting as Mock).mockReturnValue({ ...EMPTY_QUERY });
  (useImageStatus as Mock).mockReturnValue({ ...EMPTY_QUERY, data: { engines: [] } });
  (useSaveProviders as Mock).mockReturnValue({ mutate: save, isPending: false, isError: false, error: null });
  (useProviders as Mock).mockReturnValue({
    ...EMPTY_QUERY,
    data: {
      order: ['local', 'openrouter'],
      providers: [
        provider('local', { requires_key: false, api_key_env: [], position: 0 }),
        provider('openrouter', { configured: false, position: 1 }),
      ],
      warnings: [],
      config_path: '/home/jacob/Projects/kitty/config/providers.json',
    },
  });
});

afterEach(cleanup);

describe('provider call order', () => {
  it('lists the chain in call order', () => {
    render(<ProviderCenter />);
    expect(screen.getByText('local')).toBeInTheDocument();
    expect(screen.getByText('openrouter')).toBeInTheDocument();
  });

  it('marks a provider with no key as not ready', () => {
    render(<ProviderCenter />);
    expect(screen.getByText(/OPENROUTER_API_KEY missing/)).toBeInTheDocument();
  });

  it('says when a provider needs no key at all', () => {
    render(<ProviderCenter />);
    expect(screen.getByText(/no key needed/)).toBeInTheDocument();
  });

  it('moving a provider up saves the swapped order', () => {
    render(<ProviderCenter />);
    fireEvent.click(screen.getByLabelText('Move openrouter up'));
    expect(save).toHaveBeenCalledWith({ order: ['openrouter', 'local'], disabled: [] });
  });

  it('cannot move the first provider up', () => {
    render(<ProviderCenter />);
    expect(screen.getByLabelText('Move local up')).toBeDisabled();
  });

  it('cannot move the last provider down', () => {
    render(<ProviderCenter />);
    expect(screen.getByLabelText('Move openrouter down')).toBeDisabled();
  });

  it('turning a provider off saves it as disabled', () => {
    render(<ProviderCenter />);
    fireEvent.click(screen.getByLabelText('Disable openrouter'));
    expect(save).toHaveBeenCalledWith({ order: ['local', 'openrouter'], disabled: ['openrouter'] });
  });

  it('turning a disabled provider back on clears it', () => {
    (useProviders as Mock).mockReturnValue({
      ...EMPTY_QUERY,
      data: {
        order: ['local'],
        providers: [
          provider('local', { requires_key: false, api_key_env: [], position: 0 }),
          provider('openrouter', { disabled: true, position: null }),
        ],
        warnings: [],
        config_path: '/tmp/providers.json',
      },
    });
    render(<ProviderCenter />);
    fireEvent.click(screen.getByLabelText('Enable openrouter'));
    expect(save).toHaveBeenCalledWith({ order: ['local'], disabled: [] });
  });

  it('surfaces a rejected save instead of looking successful', () => {
    (useSaveProviders as Mock).mockReturnValue({
      mutate: save, isPending: false, isError: true, error: new Error('unknown provider(s): nope'),
    });
    render(<ProviderCenter />);
    expect(screen.getByText(/couldn't save/)).toBeInTheDocument();
    expect(screen.getByText(/unknown provider/)).toBeInTheDocument();
  });

  it('surfaces gateway warnings about the chain', () => {
    (useProviders as Mock).mockReturnValue({
      ...EMPTY_QUERY,
      data: {
        order: ['openrouter', 'local'],
        providers: [provider('openrouter', { configured: false, position: 0 })],
        warnings: ["first choice 'openrouter' has no key, so calls actually start at 'local'"],
        config_path: '/tmp/providers.json',
      },
    });
    render(<ProviderCenter />);
    expect(screen.getByText(/calls actually start at 'local'/)).toBeInTheDocument();
  });
});
