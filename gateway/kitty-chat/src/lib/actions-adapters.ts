/** OK-ACTION-01 — two real domain adapters for the shared action contract. */
import type {
  KittyAvailableAction,
  KittyDestination,
  KittyObjectProjection,
  KittyTruthState,
} from './actions-contract'
import type { GatewayNextStep, GatewayProject, GatewayProjectWorkItem } from './gateway'

function projectDestination(projectId: number): KittyDestination {
  return { screen: 'projects', params: { projectId }, label: 'Open Project' }
}

function workDestination(workId: string): KittyDestination {
  return { screen: 'work', params: { workId }, label: 'Open Work' }
}

function mapProjectStatus(project: GatewayProject): KittyTruthState | undefined {
  if (project.status === 'active') return 'ready'
  if (project.status === 'completed') return 'succeeded'
  if (project.status === 'failed') return 'failed'
  if (project.status === 'paused') return 'waiting_for_user'
  return undefined
}

function mapWorkStatus(item: GatewayProjectWorkItem): KittyTruthState {
  if (item.state === 'active') return 'running'
  if (item.state === 'completed') return 'succeeded'
  if (item.state === 'failed') return 'failed'
  if (item.state === 'blocked' || item.state === 'paused') return 'waiting_for_user'
  if (item.state === 'ready') return 'ready'
  if (item.state === 'waiting') return 'queued'
  return 'unknown'
}

export function projectToKittyObject(
  project: GatewayProject,
  nextStep?: GatewayNextStep | null,
): KittyObjectProjection {
  const destination = projectDestination(project.id)
  const actions: KittyAvailableAction[] = nextStep
    ? [{
        id: `project-${project.id}-next-step`,
        label: nextStep.step,
        kind: 'next_step',
        prominence: 'primary',
        enabled: true,
        destination,
      }]
    : [{
        id: `project-${project.id}-next-step`,
        label: 'Continue project',
        kind: 'next_step',
        prominence: 'primary',
        enabled: false,
        unavailableReason: 'No next step has been generated for this project yet.',
      }]

  return {
    object: {
      type: 'project',
      id: String(project.id),
      title: project.name,
      subtitle: project.kind === 'code' ? 'Development' : 'Life',
      destination,
      truthState: mapProjectStatus(project),
      projectId: String(project.id),
      owner: 'jacob',
      detail: { summary: project.summary, kind: project.kind },
    },
    actions,
  }
}

export function workItemToKittyObject(item: GatewayProjectWorkItem): KittyObjectProjection {
  const destination = workDestination(item.id)
  return {
    object: {
      type: 'work',
      id: item.id,
      title: item.title ?? 'Builder work',
      subtitle: item.next_action ?? undefined,
      destination,
      truthState: mapWorkStatus(item),
      owner: 'builder',
      detail: { state: item.state, updated_at: item.updated_at },
    },
    actions: [{
      id: `work-${item.id}-view`,
      label: item.state === 'completed' ? 'View result' : 'Open Work',
      kind: 'view',
      prominence: 'primary',
      enabled: true,
      destination,
    }],
  }
}
