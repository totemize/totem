import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Totem',
  description: 'Operations and implementation reference for Totem devices',
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: {
    nav: [
      { text: 'Architecture', link: '/architecture/system-overview' },
      { text: 'Operations', link: '/operations/ansible' },
      { text: 'Reference', link: '/reference/totemd' },
      { text: 'Hardware', link: '/hardware/display' },
    ],
    sidebar: [
      {
        text: 'Overview',
        items: [
          { text: 'Documentation home', link: '/' },
          { text: 'System architecture', link: '/architecture/system-overview' },
        ],
      },
      {
        text: 'Operations',
        items: [
          { text: 'Ansible runbook', link: '/operations/ansible' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'Totem state catalog', link: '/reference/state-model' },
          { text: 'totemd CLI and bus', link: '/reference/totemd' },
          { text: 'Python device manager', link: '/reference/device-manager' },
          { text: 'FIPS', link: '/reference/fips' },
          { text: 'strfry', link: '/reference/strfry' },
        ],
      },
      {
        text: 'Hardware',
        items: [
          { text: 'E-Ink displays', link: '/hardware/display' },
        ],
      },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/totemize/totem' },
    ],
    search: {
      provider: 'local',
    },
    outline: {
      level: [2, 3],
    },
    footer: {
      message: 'Totem is released into the public domain under the Unlicense.',
    },
  },
})
