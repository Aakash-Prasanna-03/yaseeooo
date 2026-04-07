import { create } from 'zustand'

type Goal = 'traffic' | 'brand_awareness' | 'lead_generation'

type Onboarding = {
  businessName: string
  businessDescription: string
  websiteUrl: string
  competitors: string
  targetAudience: string
  platforms: string[]
  primaryGoal: Goal | ''
}

type WsState = {
  workspaceId: string | null
  onboarding: Onboarding
  brandColors: { primary: string; secondary: string; accent: string }
  setWorkspaceId: (id: string | null) => void
  setOnboarding: (p: Partial<Onboarding>) => void
  setBrandColors: (c: Partial<WsState['brandColors']>) => void
}

const defaultColors = { primary: '#7c3aed', secondary: '#6366f1', accent: '#f97316' }

export const useWorkspaceStore = create<WsState>((set) => ({
  workspaceId: null,
  brandColors: defaultColors,
  onboarding: {
    businessName: '',
    businessDescription: '',
    websiteUrl: '',
    competitors: '',
    targetAudience: '',
    platforms: [],
    primaryGoal: '',
  },
  setWorkspaceId: (id) => set({ workspaceId: id }),
  setOnboarding: (p) => set((s) => ({ onboarding: { ...s.onboarding, ...p } })),
  setBrandColors: (c) => set((s) => ({ brandColors: { ...s.brandColors, ...c } })),
}))
