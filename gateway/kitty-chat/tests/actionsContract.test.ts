import { describe, expect, it } from 'vitest'
import type { GatewayProject, GatewayNextStep, GatewayProjectWorkItem } from '@/lib/gateway'
import type { KittyAvailableAction, KittyObjectProjection, KittyObjectRef } from '@/lib/actions-contract'
import { projectToKittyObject, workItemToKittyObject } from '@/lib/actions-adapters'

const activeProject: GatewayProject = {
  id: 42, name: 'Kitty Home Page', kind: 'code', status: 'active',
  summary: 'Building the new Home view', paths: ['/code/kitty'], last_touched: 1700000000,
  open_questions: [], next_actions: [], links: [],
}

const completedProject: GatewayProject = { ...activeProject, id: 7, name: 'Finished project', status: 'completed' }

const nextStep: GatewayNextStep = {
  project_id: 42, step: 'Review the home page mockups', why: 'They are ready',
  recent_win: 'The brief renders', delegable: false, generated_at: 1700000000,
}

const activeWork: GatewayProjectWorkItem = {
  id: 'initiative-alpha', title: 'Ship action grammar', state: 'active',
  next_action: 'Watch the current run', updated_at: '2026-09-03T10:00:00Z',
}

const waitingWork: GatewayProjectWorkItem = {
  id: 'initiative-beta', title: 'Await dependency', state: 'waiting',
  next_action: 'Wait for dependency', updated_at: '2026-09-03T09:00:00Z',
}

describe('actions-contract types', () => {
  it('KittyObjectRef has required fields', () => {
    const ref: KittyObjectRef = { type: 'project', id: '42', title: 'Test', owner: 'jacob' }
    expect(ref).toMatchObject({ type: 'project', id: '42', title: 'Test', owner: 'jacob' })
  })

  it('KittyAvailableAction supports explicit unavailable reasons', () => {
    const action: KittyAvailableAction = {
      id: 'x', label: 'Do it', kind: 'generic', prominence: 'primary', enabled: false,
      unavailableReason: 'Not ready yet',
    }
    expect(action.enabled).toBe(false)
    expect(action.unavailableReason).toBe('Not ready yet')
  })

  it('KittyObjectProjection contains object plus actions', () => {
    const projection: KittyObjectProjection = {
      object: { type: 'project', id: '1', title: 'X', owner: 'jacob' }, actions: [],
    }
    expect(projection.actions).toEqual([])
  })
})

describe('project projection', () => {
  it('uses the real native Projects destination instead of inventing a URL', () => {
    const result = projectToKittyObject(activeProject, nextStep)
    expect(result.object.destination).toEqual({
      screen: 'projects', params: { projectId: 42 }, label: 'Open Project',
    })
    expect(result.object.destination).not.toHaveProperty('path')
  })

  it('uses the same real destination for the project next-step navigation action', () => {
    const action = projectToKittyObject(activeProject, nextStep).actions.find(item => item.kind === 'next_step')
    expect(action?.destination).toEqual({
      screen: 'projects', params: { projectId: 42 }, label: 'Open Project',
    })
  })

  it('maps an active project to ready, not running work', () => {
    expect(projectToKittyObject(activeProject).object.truthState).toBe('ready')
  })

  it('maps completed project to succeeded', () => {
    expect(projectToKittyObject(completedProject).object.truthState).toBe('succeeded')
  })

  it('keeps a disabled next-step action visible with a reason', () => {
    const action = projectToKittyObject(completedProject).actions.find(item => item.kind === 'next_step')
    expect(action).toMatchObject({ enabled: false })
    expect(action?.unavailableReason).toBeTruthy()
  })

  it('has stable identity across repeated projections', () => {
    expect(projectToKittyObject(activeProject).object.id).toBe(projectToKittyObject(activeProject).object.id)
  })
})

describe('work projection', () => {
  it('projects the second proof domain through the native Work destination', () => {
    const result = workItemToKittyObject(activeWork)
    expect(result.object.type).toBe('work')
    expect(result.object.id).toBe('initiative-alpha')
    expect(result.object.destination).toEqual({
      screen: 'work', params: { workId: 'initiative-alpha' }, label: 'Open Work',
    })
  })

  it('maps active work to running', () => {
    expect(workItemToKittyObject(activeWork).object.truthState).toBe('running')
  })

  it('maps waiting work to queued rather than running or failed', () => {
    expect(workItemToKittyObject(waitingWork).object.truthState).toBe('queued')
  })

  it('always exposes a real navigation action to the Work surface', () => {
    const action = workItemToKittyObject(activeWork).actions[0]
    expect(action).toMatchObject({ kind: 'view', enabled: true })
    expect(action.destination?.screen).toBe('work')
  })

  it('has stable identity across repeated projections', () => {
    expect(workItemToKittyObject(activeWork).object.id).toBe(workItemToKittyObject(activeWork).object.id)
  })
})
