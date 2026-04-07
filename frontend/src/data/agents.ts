export const AGENTS = [
  {
    name: 'Maya',
    role: 'Lead Writer',
    platforms: 'Blogs, long-form, landing pages',
    tagline: 'Sets the voice. Orchestrates every line of narrative.',
    color: '#a78bfa',
  },
  {
    name: 'Sam',
    role: 'Blog Specialist',
    platforms: 'WordPress, Medium, Substack',
    tagline: 'Topical clusters and interlinks for authority.',
    color: '#34d399',
  },
  {
    name: 'Zoe',
    role: 'Social Copy',
    platforms: 'LinkedIn, X, Facebook',
    tagline: 'Sharp hooks without the hustle-bro noise.',
    color: '#f472b6',
  },
  {
    name: 'Leo',
    role: 'Community',
    platforms: 'Reddit, Quora, forums',
    tagline: 'Helpful first. Promotional only when it truly fits.',
    color: '#fb923c',
  },
  {
    name: 'Aria',
    role: 'GEO',
    platforms: 'ChatGPT, Perplexity, AI Overviews',
    tagline: 'Entity-rich answers engines want to cite.',
    color: '#38bdf8',
  },
  {
    name: 'Finn',
    role: 'Outreach',
    platforms: 'Email, PR, guest posts',
    tagline: 'Polite persistence for links that compound.',
    color: '#fbbf24',
  },
  {
    name: 'Nova',
    role: 'Analytics',
    platforms: 'Signals → rest of team',
    tagline: 'Measures what moved. Briefs Maya and Leo with receipts.',
    color: '#c4b5fd',
  },
] as const

export type AgentName = (typeof AGENTS)[number]['name']
