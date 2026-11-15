import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

vi.mock('./components/HeroVisual', () => ({ default: () => null }))
vi.mock('./components/SpaceExperience', () => ({ default: () => null }))

const frames = [0, 1].map((index) => ({
  index,
  product_id: `product-${index}`,
  observation_id: `observation-${index}`,
  timestamp: `2026-08-18T20:4${index}:00Z`,
  obs_time: `2026-08-18T20:4${index}:00Z`,
  collection: 'spherex_qr3',
  band: 'SPHEREx-D2',
  preview_url: `/api/media/job-1/frame-${index}.png`,
  preview_stretch_urls: {
    linear: `/api/media/job-1/frame-${index}.png`,
    log: `/api/media/job-1/frame-${index}-log.png`,
    sqrt: `/api/media/job-1/frame-${index}-sqrt.png`,
    asinh: `/api/media/job-1/frame-${index}-asinh.png`,
  },
  mask_overlay_urls: {
    linear: `/api/media/job-1/frame-${index}-mask.png`,
    log: `/api/media/job-1/frame-${index}-mask-log.png`,
    sqrt: `/api/media/job-1/frame-${index}-mask-sqrt.png`,
    asinh: `/api/media/job-1/frame-${index}-mask-asinh.png`,
  },
}))

const candidates = [
  { candidate_id: 'motion-1', classification: 'possible motion', ra_deg: 10, dec_deg: 2, max_abs_significance: 7, scientific_caveat: 'Needs review' },
  { candidate_id: 'variable-1', classification: 'possible brightness variability', ra_deg: 11, dec_deg: 3, flux_change_significance: 6, scientific_caveat: 'Needs review' },
]

const result = {
  job_id: 'job-1',
  status: 'complete',
  query: { ra: 10, dec: 2, fov: 0.5 },
  frames,
  comparisons: [{
    status: 'complete',
    alignment: { matches: 8 },
    psf_matching: { status: 'complete' },
    noise_covariance: { status: 'empirically_estimated', blank_sky_samples: 1500 },
    difference_url: '/api/media/job-1/difference.png',
    significance_url: '/api/media/job-1/significance.png',
  }],
  candidates,
  candidate_summary: { total_records: 4, reviewable_signals: 2, ambiguous_or_unclassified: 2 },
  warnings: [],
}

let requests
let searchResponse
let jobResponse
let resultResponse

function jsonResponse(payload, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload }
}

async function openSearch(user) {
  await user.click(screen.getByRole('button', { name: /search the sky/i }))
  return screen.findByRole('button', { name: /search observations/i })
}

async function runSearch(user) {
  await openSearch(user)
  await user.type(screen.getByLabelText('Right Ascension (RA)'), '10')
  await user.type(screen.getByLabelText('Declination (Dec)'), '2')
  await user.click(screen.getByRole('button', { name: /search observations/i }))
  await screen.findByText(/2 real observations processed/i)
}

beforeEach(() => {
  requests = []
  searchResponse = {
    search_id: 'search-1', count: 2,
    observations: [{ observation_id: 'observation-0', band: 'SPHEREx-D2' }, { observation_id: 'observation-1', band: 'SPHEREx-D2' }],
    recommended_observation_ids: ['observation-0', 'observation-1'],
    recommended_selection: { observation_count: 2, band: 'SPHEREx-D2', distinct_dates: 2, baseline_days: 35 },
  }
  jobResponse = { job_id: 'job-1', status: 'complete' }
  resultResponse = result
  globalThis.fetch = vi.fn(async (url, options = {}) => {
    requests.push({ url: String(url), options })
    if (String(url).endsWith('/api/targets')) return jsonResponse({ targets: [], warnings: [] })
    if (String(url).endsWith('/api/search')) return jsonResponse(searchResponse)
    if (String(url).endsWith('/api/jobs')) return jsonResponse(jobResponse)
    if (String(url).endsWith('/api/results/job-1')) return jsonResponse(resultResponse)
    return jsonResponse({ status: 'complete' })
  })
})

afterEach(() => {
  cleanup()
  delete URL.createObjectURL
  delete URL.revokeObjectURL
  window.history.replaceState({}, '', '/')
})

describe('SPHEREx Explorer core flows', () => {
  it('submits coordinates, release, band and date filters and preserves them in the share URL', async () => {
    const user = userEvent.setup()
    render(<App />)
    await openSearch(user)
    await user.type(screen.getByLabelText('Right Ascension (RA)'), '10')
    await user.type(screen.getByLabelText('Declination (Dec)'), '2')
    await user.selectOptions(screen.getByLabelText('Field of View'), '0.5')
    await user.selectOptions(screen.getByLabelText('Data Release'), 'QR3')
    await user.selectOptions(screen.getByLabelText('Spectral Band (optional)'), 'SPHEREx-D2')
    await user.type(screen.getByLabelText('Start date (optional)'), '2026-08-18')
    await user.type(screen.getByLabelText('End date (optional)'), '2026-08-19')
    await user.click(screen.getByRole('button', { name: /search observations/i }))
    await screen.findByText(/2 real observations processed/i)

    const request = requests.find((item) => item.url.endsWith('/api/search'))
    expect(JSON.parse(request.options.body)).toMatchObject({
      ra: 10, dec: 2, fov: 0.5, data_release: 'QR3', band: 'SPHEREx-D2',
      date_start: '2026-08-18', date_end: '2026-08-19',
    })
    const params = new URLSearchParams(window.location.search)
    expect(params.get('ra')).toBe('10')
    expect(params.get('date_start')).toBe('2026-08-18')
    expect(params.get('date_end')).toBe('2026-08-19')
    expect(params.get('band')).toBe('SPHEREx-D2')
  })

  it('supports previous, next, play/pause and displays the API timestamp', async () => {
    const user = userEvent.setup()
    render(<App />)
    await runSearch(user)
    await user.click(screen.getByRole('button', { name: /back to destinations/i }))
    await user.click(screen.getByRole('button', { name: /timeline & blink/i }))
    expect(screen.getByText('2026-08-18T20:40:00Z')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getAllByText('2 / 2')).toHaveLength(2)
    await user.selectOptions(screen.getByLabelText('PLAYBACK SPEED'), '4x')
    await user.click(screen.getByRole('button', { name: /^play$/i }))
    expect(screen.getByRole('button', { name: /^pause$/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^pause$/i }))
    await user.click(screen.getByRole('button', { name: /previous/i }))
    expect(screen.getByText('product-0 · spherex_qr3')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Observation frame position'), { target: { value: '1' } })
    expect(screen.getByText('product-1 · spherex_qr3')).toBeInTheDocument()
  })

  it('switches real frame/difference/significance modes and image display controls', async () => {
    const user = userEvent.setup()
    render(<App />)
    await runSearch(user)
    await user.click(screen.getByRole('button', { name: /back to destinations/i }))
    await user.click(screen.getByRole('button', { name: /image comparison/i }))
    await user.click(screen.getByRole('button', { name: /original frames/i }))
    expect(screen.getByAltText('First SPHEREx observation')).toHaveAttribute('src', frames[0].preview_url)
    await user.click(screen.getByRole('button', { name: /difference image/i }))
    expect(screen.getByAltText('Real SPHEREx difference image')).toHaveAttribute('src', result.comparisons[0].difference_url)
    await user.click(screen.getByRole('button', { name: /significance image/i }))
    expect(screen.getByAltText('Real SPHEREx significance image')).toHaveAttribute('src', result.comparisons[0].significance_url)
    await user.click(screen.getByRole('button', { name: /back to destinations/i }))
    await user.click(screen.getByRole('button', { name: /image viewer/i }))
    await user.click(screen.getByRole('button', { name: 'Image' }))
    await user.selectOptions(screen.getByLabelText('INTENSITY SCALING'), 'log')
    await user.click(screen.getByLabelText(/show data mask overlay/i))
    expect(screen.getByAltText(/SPHEREx observation product-0/i)).toHaveAttribute('src', frames[0].mask_overlay_urls.log)
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute('download', 'product-0.png')
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute('href', frames[0].preview_url)
    await user.click(screen.getByRole('button', { name: 'Compare' }))
    expect(screen.getByRole('heading', { name: 'Compare Observations' })).toBeInTheDocument()
  })

  it('filters candidate classes and triggers CSV/JSON report downloads', async () => {
    const user = userEvent.setup()
    const createUrl = vi.fn(() => 'blob:test-report')
    const revokeUrl = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    URL.createObjectURL = createUrl
    URL.revokeObjectURL = revokeUrl
    const { container } = render(<App />)
    await runSearch(user)
    await user.click(screen.getByRole('button', { name: /back to destinations/i }))
    await user.click(screen.getByRole('button', { name: /candidate review/i }))
    expect(container.querySelectorAll('.candidate-table article')).toHaveLength(2)
    await user.selectOptions(screen.getByDisplayValue('All reviewable signals'), 'possible motion')
    expect(container.querySelectorAll('.candidate-table article')).toHaveLength(1)
    expect(container.querySelector('.candidate-table').textContent).toContain('possible motion')
    await user.click(screen.getByRole('button', { name: /export csv/i }))
    await user.click(screen.getByRole('button', { name: /export json/i }))
    expect(createUrl).toHaveBeenCalledTimes(2)
    expect(click).toHaveBeenCalledTimes(2)
    await waitFor(() => expect(revokeUrl).toHaveBeenCalledTimes(2), { timeout: 2000 })
  })

  it('shows an honest no-coverage response without starting a processing job', async () => {
    searchResponse = { search_id: 'empty-search', count: 0, observations: [], message: 'No matching SPHEREx observations were returned.' }
    const user = userEvent.setup()
    render(<App />)
    await openSearch(user)
    await user.type(screen.getByLabelText('Right Ascension (RA)'), '10')
    await user.type(screen.getByLabelText('Declination (Dec)'), '2')
    await user.click(screen.getByRole('button', { name: /search observations/i }))
    expect(await screen.findByText('No matching SPHEREx observations were returned.')).toBeInTheDocument()
    expect(requests.some((item) => item.url.endsWith('/api/jobs'))).toBe(false)
  })

  it('shows metadata and provenance for a processed archive frame', async () => {
    const user = userEvent.setup()
    render(<App />)
    await runSearch(user)
    await user.click(screen.getByRole('button', { name: /back to destinations/i }))
    await user.click(screen.getByRole('button', { name: /metadata & provenance/i }))
    expect(screen.getByText('NASA / IPAC Infrared Science Archive (IRSA)')).toBeInTheDocument()
    expect(screen.getByText('product-0')).toBeInTheDocument()
    expect(screen.getAllByText('spherex_qr3')).toHaveLength(2)
  })

  it('returns the Explore Again button to the top of the page', async () => {
    const user = userEvent.setup()
    const scroll = vi.spyOn(window, 'scrollTo')
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Explore Again' }))
    expect(scroll).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
  })

  it('reports a processing failure and disables blink playback for a single frame', async () => {
    const user = userEvent.setup()
    jobResponse = { job_id: 'job-1', status: 'failed', error: 'Real FITS download failed' }
    render(<App />)
    await openSearch(user)
    await user.type(screen.getByLabelText('Right Ascension (RA)'), '10')
    await user.type(screen.getByLabelText('Declination (Dec)'), '2')
    await user.click(screen.getByRole('button', { name: /search observations/i }))
    expect(await screen.findByText('Real FITS download failed')).toBeInTheDocument()

    jobResponse = { job_id: 'job-1', status: 'complete' }
    searchResponse = {
      search_id: 'search-1', count: 1,
      observations: [{ observation_id: 'observation-0', band: 'SPHEREx-D2' }],
      recommended_observation_ids: ['observation-0'],
      recommended_selection: { observation_count: 1, band: 'SPHEREx-D2', distinct_dates: 1, baseline_days: 0 },
    }
    resultResponse = { ...result, frames: [frames[0]], comparisons: [], candidates: [], candidate_summary: { total_records: 0, reviewable_signals: 0, ambiguous_or_unclassified: 0 } }
    await user.click(screen.getByRole('button', { name: /search observations/i }))
    await screen.findByText(/1 real observations processed/i)
    await user.click(screen.getByRole('button', { name: /back to destinations/i }))
    await user.click(screen.getByRole('button', { name: /timeline & blink/i }))
    expect(screen.getByText('One frame available')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^play$/i })).toBeDisabled()
  })
})
