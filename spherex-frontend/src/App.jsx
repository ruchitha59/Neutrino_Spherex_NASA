
import './App.css'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'

const HeroVisual = lazy(() => import('./components/HeroVisual'))
const SpaceExperience = lazy(() => import('./components/SpaceExperience'))

async function postSearchWithRetry(payload) {
  let lastError
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetch('/api/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (response.ok || ![502, 503, 504].includes(response.status) || attempt === 2) return response
      lastError = new Error(`Archive search temporarily failed (${response.status})`)
    } catch (error) {
      lastError = error
      if (attempt === 2) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, 1000 * (attempt + 1)))
  }
  throw lastError
}

const MASK_FLAG_LABELS = {
  flag_CHI: 'High chi-square fit', flag_DICHROIC: 'Dichroic artifact', flag_GHOST: 'Ghost image',
  flag_GHOST_FPA: 'Ghost from detector assembly', flag_GHOST_EXT: 'Extended ghost artifact',
  flag_HALO: 'Bright-source halo', flag_HOT: 'Hot detector pixel', flag_OUTLIER: 'Outlier pixel',
  flag_STREAK: 'Image streak', flag_MISSING_DATA: 'Missing detector data', flag_CROSSTALK: 'Detector cross-talk',
  flag_SNOWBALL: 'Cosmic-ray snowball', flag_PHANMISS: 'Missing phantom correction',
  flag_TRANSIENT: 'Transient artifact', flag_NONLINEAR: 'Detector non-linearity', flag_OVERFLOW: 'Signal overflow',
  flag_COLD: 'Cold detector pixel', flag_PERSIST: 'Persistence from earlier exposure', flag_SUR_ERROR: 'Surface-brightness error',
  flag_PERSIST2: 'Strong persistence artifact', flag_BLOOM: 'Charge bleed from a bright pixel', flag_HALO2: 'Extended halo artifact',
}

function readQualitySummary(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  try { return JSON.parse(value) } catch { return null }
}


function App() {
  const [activeViewerTab, setActiveViewerTab] = useState('Image')
  const [activeWorkspace, setActiveWorkspace] = useState('home')
  const [ra, setRa] = useState(() => new URLSearchParams(window.location.search).get('ra') || '')
  const [dec, setDec] = useState(() => new URLSearchParams(window.location.search).get('dec') || '')

  const [timelineSpeed, setTimelineSpeed] = useState('1x')
  const [timelineFrames, setTimelineFrames] = useState([])
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [comparisonAIndex, setComparisonAIndex] = useState(0)
  const [comparisonBIndex, setComparisonBIndex] = useState(1)
  const [selectedPairResult, setSelectedPairResult] = useState(null)
  const [isComparingSelectedPair, setIsComparingSelectedPair] = useState(false)
  const [pairComparisonMessage, setPairComparisonMessage] = useState('')
  const [isTimelinePlaying, setIsTimelinePlaying] = useState(false)

useEffect(() => {
  if (!isTimelinePlaying || timelineFrames.length < 2) return

  const speed = Number(timelineSpeed.replace('x', ''))

  const timer = setInterval(() => {
    setCurrentFrameIndex((current) =>
      (current + 1) % timelineFrames.length
    )
  }, 1000 / speed)

  return () => clearInterval(timer)
}, [isTimelinePlaying, timelineFrames.length, timelineSpeed])

const handlePreviousFrame = () => {
  setIsTimelinePlaying(false)
  setCurrentFrameIndex((current) =>
    Math.max(0, current - 1)
  )
}

const handleNextFrame = () => {
  setIsTimelinePlaying(false)
  setCurrentFrameIndex((current) =>
    Math.min(timelineFrames.length - 1, current + 1)
  )
}

const handleTimelinePlay = () => {
  if (timelineFrames.length < 2) return
  setIsTimelinePlaying((playing) => !playing)
}

const handleFrameChange = (value) => {
  setIsTimelinePlaying(false)
  setCurrentFrameIndex(Number(value))
}
const currentFrame = timelineFrames[currentFrameIndex] || null

  const [comparisonMode, setComparisonMode] = useState('original')
  const [intensityScaling, setIntensityScaling] = useState('linear')
  const [contrast, setContrast] = useState(50)
  const [brightness, setBrightness] = useState(50)
  const [showMask, setShowMask] = useState(false)
  const [candidateFilter, setCandidateFilter] = useState('all')

  const [fov, setFov] = useState(() => new URLSearchParams(window.location.search).get('fov') || '0.5')
  const [dataRelease, setDataRelease] = useState(() => new URLSearchParams(window.location.search).get('release') || 'QR3')
  const [band, setBand] = useState(() => new URLSearchParams(window.location.search).get('band') || '')
  const [dateStart, setDateStart] = useState(() => new URLSearchParams(window.location.search).get('date_start') || '')
  const [dateEnd, setDateEnd] = useState(() => new URLSearchParams(window.location.search).get('date_end') || '')
  const [searchMessage, setSearchMessage] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [observations, setObservations] = useState([])
  const [processingResult, setProcessingResult] = useState(null)
  const currentComparison = processingResult?.comparisons?.find((item) => item.status === 'complete')
  const selectedComparison = (selectedPairResult?.comparisons || processingResult?.comparisons || []).find((item) => item.status === 'complete' && ((!item.reference_observation_id && !item.comparison_observation_id && comparisonAIndex === 0 && comparisonBIndex === 1) || ([item.reference_observation_id, item.comparison_observation_id].includes(timelineFrames[comparisonAIndex]?.product_id) && [item.reference_observation_id, item.comparison_observation_id].includes(timelineFrames[comparisonBIndex]?.product_id))))
  const blockedComparison = processingResult?.comparisons?.find((item) => item.status !== 'complete')
  const candidateRecords = processingResult?.candidates || []
  const reviewCandidates = candidateRecords.filter((candidate) => ['possible motion', 'possible brightness variability'].includes(candidate.classification))
  const filteredReviewCandidates = candidateFilter === 'all'
    ? reviewCandidates
    : reviewCandidates.filter((candidate) => candidate.classification === candidateFilter)
  const ambiguousCandidateCount = processingResult?.candidate_summary?.ambiguous_or_unclassified ?? Math.max(0, candidateRecords.length - reviewCandidates.length)
  const viewerImageUrl = currentFrame
    ? (showMask
      ? currentFrame.mask_overlay_urls?.[intensityScaling]
      : currentFrame.preview_stretch_urls?.[intensityScaling]) || currentFrame.preview_url
    : null
  const viewerImageStyle = { filter: `brightness(${brightness / 50}) contrast(${contrast / 50})` }
  const qualitySummary = readQualitySummary(currentFrame?.quality_summary)
  const qualityFlags = qualitySummary ? Object.entries(qualitySummary).filter(([key, count]) => key.startsWith('flag_') && Number(count) > 0) : []
  const [apiError, setApiError] = useState('')
  const [targets, setTargets] = useState([])
  const [selectedTarget, setSelectedTarget] = useState(() => new URLSearchParams(window.location.search).get('target') || '')

  useEffect(() => {
    fetch('/api/targets').then((response) => response.ok ? response.json() : Promise.reject(new Error('Target catalog unavailable')))
      .then((payload) => {
        const resolved = payload.targets || []
        setTargets(resolved)
        const target = resolved.find((item) => item.id === new URLSearchParams(window.location.search).get('target'))
        if (target) {
          setRa(String(target.ra))
          setDec(String(target.dec))
        }
      })
      .catch(() => setTargets([]))
  }, [])

  const selectTarget = (id) => {
    setSelectedTarget(id)
    const target = targets.find((item) => item.id === id)
    if (target) {
      setRa(String(target.ra))
      setDec(String(target.dec))
      setSearchMessage(`${target.name} coordinates resolved by ${target.coordinate_source || 'the connected target catalog'}.`)
    }
  }

  const homeScrollPosition = useRef(0)

const openWorkspace = (workspace) => {
  homeScrollPosition.current = window.scrollY
  setActiveWorkspace(workspace)
}

const returnToDestinations = () => {
  setActiveWorkspace('home')
}

const downloadCandidateReport = (format) => {
  if (!processingResult) return
  const report = {
    job_id: processingResult.job_id,
    status: processingResult.status,
    query: processingResult.query,
    generated_at_utc: new Date().toISOString(),
    candidate_summary: processingResult.candidate_summary,
    candidates: reviewCandidates,
    scientific_note: 'Candidate labels are preliminary and are not confirmed discoveries.',
  }
  const columns = ['candidate_id', 'classification', 'ra_deg', 'dec_deg', 'significance', 'scientific_caveat', 'classification_rationale']
  const rows = reviewCandidates.map((candidate) => ({
    candidate_id: candidate.candidate_id,
    classification: candidate.classification,
    ra_deg: candidate.ra_deg,
    dec_deg: candidate.dec_deg,
    significance: candidate.max_abs_significance ?? candidate.flux_change_significance,
    scientific_caveat: candidate.scientific_caveat,
    classification_rationale: candidate.classification_rationale,
  }))
  const csvValue = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const content = format === 'csv'
    ? [columns.join(','), ...rows.map((row) => columns.map((column) => csvValue(row[column])).join(','))].join('\r\n')
    : JSON.stringify(report, null, 2)
  const blob = new Blob([content], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `spherex-candidates-${processingResult.job_id || 'report'}.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

  const isValidCoordinates =
  ra !== '' &&
  dec !== '' &&
  Number(ra) >= 0 &&
  Number(ra) < 360 &&
  Number(dec) >= -90 &&
  Number(dec) <= 90
  const handleSearch = async () => {
    const share = new URL(window.location.href)
    share.searchParams.set('ra', ra)
    share.searchParams.set('dec', dec)
    share.searchParams.set('fov', fov)
    share.searchParams.set('release', dataRelease)
    if (selectedTarget) share.searchParams.set('target', selectedTarget)
    else share.searchParams.delete('target')
    if (band) share.searchParams.set('band', band)
    else share.searchParams.delete('band')
    if (dateStart) share.searchParams.set('date_start', dateStart)
    else share.searchParams.delete('date_start')
    if (dateEnd) share.searchParams.set('date_end', dateEnd)
    else share.searchParams.delete('date_end')
    window.history.replaceState({}, '', share)
    setIsSearching(true)
    setApiError('')
    setProcessingResult(null)
    setObservations([])
    setTimelineFrames([])
    setIsTimelinePlaying(false)
    setSearchMessage('Searching the live NASA/IPAC IRSA archive…')
    try {
      const response = await postSearchWithRetry({ ra: Number(ra), dec: Number(dec), fov: Number(fov), dataRelease, data_release: dataRelease, target_id: selectedTarget || null, band: band || null, date_start: dateStart || null, date_end: dateEnd || null, limit: 20 })
      const found = await response.json()
      if (!response.ok) throw new Error(found.detail || 'Archive search failed')
      setObservations(found.observations || [])
      if (!found.observations?.length) {
        setSearchMessage(found.message || 'No matching observation found in the collections checked.')
        return
      }
      const recommendedSelection = found.recommended_selection
      setSearchMessage(`${found.count} real archive observation${found.count === 1 ? '' : 's'} found. Preparing ${recommendedSelection?.observation_count || 0} ${recommendedSelection?.band || 'same-band'} frames across ${recommendedSelection?.distinct_dates || 0} dates (${recommendedSelection?.baseline_days || 0}-day baseline)…`)
      const byBand = (found.observations || []).reduce((groups, observation) => {
        const key = observation.band || 'unknown'
        groups[key] = [...(groups[key] || []), observation]
        return groups
      }, {})
      const recommendedIds = new Set(found.recommended_observation_ids || [])
      const selected = recommendedIds.size
        ? found.observations.filter((item) => recommendedIds.has(item.observation_id))
        : Object.values(byBand).sort((a, b) => b.length - a.length)[0]?.slice(0, 6) || []
      const jobRequest = found.search_id
        ? { search_id: found.search_id, observation_ids: selected.map((item) => item.observation_id) }
        : { ra: Number(ra), dec: Number(dec), fov: Number(fov), dataRelease, target_id: selectedTarget || null, observation_ids: selected.map((item) => item.observation_id) }
      const jobResponse = await fetch('/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobRequest),
      })
      const job = await jobResponse.json()
      if (!jobResponse.ok) throw new Error(job.detail || 'Could not start processing')
      setSearchMessage('Downloading and processing real FITS cutouts…')
      let status = job
      while (['queued', 'downloading', 'processing'].includes(status.status)) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        const statusResponse = await fetch(`/api/jobs/${job.job_id}`)
        status = await statusResponse.json()
        if (!statusResponse.ok) throw new Error(status.detail || 'Could not read processing status')
        setSearchMessage(`${status.status === 'downloading' ? 'Downloading' : 'Processing'} real observations… ${status.progress || 0}%`)
      }
      if (status.status === 'failed') throw new Error(status.error || 'Science processing failed')
      const resultResponse = await fetch(`/api/results/${job.job_id}`)
      const result = await resultResponse.json()
      if (!resultResponse.ok) throw new Error(result.detail || 'Could not retrieve processing results')
      const frames = result.frames || []
      setProcessingResult(result)
      setTimelineFrames(frames)
      setCurrentFrameIndex(0)
      setComparisonAIndex(0)
      setComparisonBIndex(Math.min(1, Math.max(0, frames.length - 1)))
      const completedComparisons = result.comparisons?.filter((item) => item.status === 'complete').length || 0
      const blocked = result.comparisons?.find((item) => item.status !== 'complete')
      const alignmentReason = blocked?.reason || blocked?.explanation?.reason
      const reviewableSignals = result.candidate_summary?.reviewable_signals ?? result.candidates?.length ?? 0
      setSearchMessage(frames.length ? `${frames.length} real observations processed. ${completedComparisons} scientifically gated comparisons available; ${reviewableSignals} signals queued for human review.${alignmentReason ? ` Alignment note: ${alignmentReason}` : ''}` : 'The archive returned observations, but none could be processed into usable frames.')
    } catch (error) {
      setApiError(error.message)
      setSearchMessage('The live search or processing request did not complete.')
    } finally {
      setIsSearching(false)
    }
  }

  const runSelectedPairComparison = async () => {
    const frameA = timelineFrames[comparisonAIndex]
    const frameB = timelineFrames[comparisonBIndex]
    if (!frameA || !frameB || frameA.product_id === frameB.product_id || !processingResult?.job_id) return
    const existing = processingResult.comparisons?.find((item) => item.reference_observation_id === frameA.product_id && item.comparison_observation_id === frameB.product_id && item.status === 'complete')
    if (existing) { setSelectedPairResult(null); setPairComparisonMessage('This selected pair already has a valid processed comparison.'); return }
    setIsComparingSelectedPair(true)
    setPairComparisonMessage('Running the selected real FITS pair through alignment, PSF matching, and noise checks…')
    try {
      const response = await fetch(`/api/jobs/${processingResult.job_id}/compare`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ observation_a_id: frameA.product_id, observation_b_id: frameB.product_id }) })
      const job = await response.json()
      if (!response.ok) throw new Error(job.detail || 'Could not start pair comparison')
      let status = job
      while (['queued', 'processing', 'downloading'].includes(status.status)) {
        await new Promise((resolve) => setTimeout(resolve, 1000))
        const poll = await fetch(`/api/jobs/${job.job_id}`)
        status = await poll.json()
        if (!poll.ok) throw new Error(status.detail || 'Could not read comparison status')
      }
      if (status.status === 'failed') throw new Error(status.error || 'Selected pair failed science validation')
      const resultResponse = await fetch(`/api/results/${job.job_id}`)
      const result = await resultResponse.json()
      if (!resultResponse.ok) throw new Error(result.detail || 'Could not retrieve comparison products')
      setSelectedPairResult(result)
      setPairComparisonMessage(result.comparisons?.some((item) => item.status === 'complete') ? 'Selected pair passed the science gates.' : 'Selected pair did not pass the science gates; no difference image was produced.')
    } catch (error) { setSelectedPairResult(null); setPairComparisonMessage(error.message) }
    finally { setIsComparingSelectedPair(false) }
  }
  
  useEffect(() => {
  const elements = document.querySelectorAll(
    '.mission-heading, .mission-card'
  )

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal-visible')
          observer.unobserve(entry.target)
        }
      })
    },
    {
      threshold: 0.15,
    }
  )

  elements.forEach((element) => observer.observe(element))

  return () => observer.disconnect()
}, [])

useEffect(() => {
  if (activeWorkspace === 'home' && homeScrollPosition.current > 0) {
    requestAnimationFrame(() => {
      window.scrollTo({
        top: homeScrollPosition.current,
        behavior: 'auto'
      })
    })
  }
}, [activeWorkspace])

useEffect(() => {
  if (activeWorkspace !== 'home') {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'instant'
    })
  }
}, [activeWorkspace])

  return (
    <div className="app">
      <Suspense fallback={null}><SpaceExperience /></Suspense>
      {activeWorkspace === 'home' && (
        <>
      <header className="navbar">
        <div className="logo">SPHEREx</div>

        <nav>
  <a href="#science">Explore</a>
  <a href="#explorer">Observations</a>
  <a href="#mission">About Mission</a>
</nav>

        <div className="mission-tag">
          NASA MISSION
        </div>
      </header>

      <main className="main-content">
        <section className="hero">
          <Suspense fallback={<div className="hero-visual-loading" aria-hidden="true" />}><HeroVisual /></Suspense>
          <div className="hero-content">
            <p className="hero-eyebrow">
              NASA · SPHEREx SPACE TELESCOPE
            </p>

            <h1>
              Explore the Universe
              <span> Beyond What We See.</span>
            </h1>

            <p className="hero-description">
              Discover the universe through infrared observations
              and explore the hidden stories of the cosmos.
            </p>

            <a href="#explorer" className="hero-button">
              Begin Exploring
            </a>
          </div>

          <div className="hero-bottom">
            <span>ALL-SKY INFRARED SURVEY</span>
            <span>SCROLL TO DISCOVER ↓</span>
          </div>
        </section>
        
<section className="mission-section" id="mission">

  <div className="mission-heading">
    <p className="section-eyebrow">
      ABOUT THE MISSION
    </p>

    <h2>
      A New Way to
      <span> See the Universe.</span>
    </h2>

    <p className="mission-description">
      SPHEREx explores the cosmos using infrared light,
      helping scientists investigate the history of the
      universe and the origins of cosmic materials.
    </p>
  </div>


<div className="mission-cards">

  <div className="mission-card">
    <div className="mission-card-inner">
      <div className="mission-card-front">
        <span className="card-number">01</span>
        <h3>Explore the Entire Sky</h3>
        <p>Hover to discover more</p>
        <span className="flip-hint">TURN TO EXPLORE ↗</span>
      </div>

      <div className="mission-card-back">
        <span className="card-number">01 / THE MISSION</span>
        <h3>A Map of the Cosmos</h3>
        <p>
          SPHEREx maps the entire sky in 102 infrared
          spectral bands, creating a unique all-sky spectral map.
        </p>
      </div>
    </div>
  </div>

  <div className="mission-card">
    <div className="mission-card-inner">
      <div className="mission-card-front">
        <span className="card-number">02</span>
        <h3>See in Infrared</h3>
        <p>Hover to discover more</p>
        <span className="flip-hint">TURN TO EXPLORE ↗</span>
      </div>

      <div className="mission-card-back">
        <span className="card-number">02 / THE SCIENCE</span>
        <h3>Beyond Visible Light</h3>
        <p>
          Infrared spectroscopy helps scientists study
          cosmic objects and materials that reveal the
          universe's history.
        </p>
      </div>
    </div>
  </div>

  <div className="mission-card">
    <div className="mission-card-inner">
      <div className="mission-card-front">
        <span className="card-number">03</span>
        <h3>Explore Real Observations</h3>
        <p>Hover to discover more</p>
        <span className="flip-hint">TURN TO EXPLORE ↗</span>
      </div>

      <div className="mission-card-back">
        <span className="card-number">03 / EXPLORATION</span>
        <h3>Your Cosmic Journey</h3>
        <p>
          Search sky coordinates and investigate actual
          available SPHEREx observations through our explorer.
        </p>
      </div>
    </div>
  </div>

</div>

</section>

{/* SPHEREx SCIENTIFIC GOALS */}

<section className="goals-section" id="goals">

  <div className="goals-heading">
    <p className="section-eyebrow">THE BIG QUESTIONS</p>

    <h2>
      Three Questions.
      <span> One Universe to Explore.</span>
    </h2>

    <p>
      SPHEREx investigates the universe on an enormous scale,
      from its earliest moments to the cosmic ingredients
      that may contribute to life.
    </p>
  </div>

  <div className="goal-chapters">

  <article className="goal-chapter">
    <div className="goal-number">01</div>

    <div className="goal-content">
      <span className="goal-label">THE BEGINNING</span>
      <h3>How did the universe begin?</h3>
      <p>
        SPHEREx studies the early universe by mapping millions of galaxies
        across the sky. Their distribution can reveal clues about cosmic
        inflation — the rapid expansion that occurred shortly after the
        Big Bang.
      </p>
    </div>

    <div className="goal-visual inflation-visual" aria-hidden="true">
      <div className="inflation-core"></div>
      <div className="inflation-wave wave-one"></div>
      <div className="inflation-wave wave-two"></div>
      <div className="inflation-wave wave-three"></div>
    </div>
  </article>


  <article className="goal-chapter goal-chapter-reverse">
    <div className="goal-number">02</div>

    <div className="goal-content">
      <span className="goal-label">COSMIC EVOLUTION</span>
      <h3>How did galaxies evolve?</h3>
      <p>
        By observing galaxies across cosmic history, SPHEREx helps
        scientists investigate how galaxies formed, grew and changed
        over billions of years.
      </p>
    </div>

    <div className="goal-visual galaxy-visual" aria-hidden="true">
      <div className="galaxy-glow"></div>
      <div className="galaxy-arm arm-one"></div>
      <div className="galaxy-arm arm-two"></div>
      <div className="galaxy-center"></div>
    </div>
  </article>


  <article className="goal-chapter">
    <div className="goal-number">03</div>

    <div className="goal-content">
      <span className="goal-label">COSMIC INGREDIENTS</span>
      <h3>Where does the water in planetary systems come from?</h3>
      <p>
        SPHEREx maps frozen water and other molecules in interstellar
        clouds, helping scientists understand the ingredients that
        may eventually become part of planets and planetary systems.
      </p>
    </div>

    <div className="goal-visual ingredients-visual" aria-hidden="true">
      <div className="molecule molecule-one"></div>
      <div className="molecule molecule-two"></div>
      <div className="molecule molecule-three"></div>
      <div className="molecule molecule-four"></div>
    </div>
  </article>

</div>

</section>

<section className="explorer"></section>

<section className="science-section" id="science">

  <div className="science-heading">
    <p className="section-eyebrow">THE SCIENCE BEHIND THE MISSION</p>

    <h2>
      How SPHEREx
      <span> Sees the Invisible.</span>
    </h2>

    <p>
      Every wavelength carries information.
      SPHEREx studies infrared light to uncover clues
      about the composition and history of the universe.
    </p>
  </div>

  <div className="science-journey">

    <div className="science-stage">
      <span>01</span>
      <h3>Capture Infrared Light</h3>
      <p>
        SPHEREx observes infrared light from galaxies,
        stars and other cosmic sources across the sky.
      </p>
    </div>

    <div className="science-connector">→</div>

    <div className="science-stage">
      <span>02</span>
      <h3>Separate the Wavelengths</h3>
      <p>
        Its instrument measures light in 102 spectral bands,
        revealing information about the sources it observes.
      </p>
    </div>

    <div className="science-connector">→</div>

    <div className="science-stage">
      <span>03</span>
      <h3>Build a Cosmic Map</h3>
      <p>
        These measurements help create an all-sky spectral
        map that scientists can use to investigate the cosmos.
      </p>
    </div>

  </div>

</section>


<section className="explorer-workspace" id="explorer">

  <div className="explorer-intro">
    <span className="explorer-eyebrow">INTERACTIVE SCIENCE</span>
    <h2>Explore the <span>Infrared Sky.</span></h2>
    <p>
      Search the SPHEREx observation archive by sky coordinates
      and investigate real observations from the mission.
    </p>
  </div>



{activeWorkspace === 'home' && (
  <div className="cosmic-navigation" id="destinations">
  <div className="cosmic-nav-heading">
    <span>THE SPHEREx OBSERVATORY</span>
    <h3>Choose your destination</h3>
    <p>Select a point in the observatory to begin exploring.</p>
  </div>

  <div className="cosmic-map">
    <svg
      className="orbit-lines"
      viewBox="0 0 800 520"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      <ellipse cx="400" cy="260" rx="330" ry="175" />
      <ellipse cx="400" cy="260" rx="245" ry="115" />
      <ellipse cx="400" cy="260" rx="150" ry="65" />
      <path d="M70 260 H730" />
      <path d="M400 65 V455" />
    </svg>

    <div className="cosmic-core">
      <span>SPHEREx</span>
      <small>OBSERVATORY</small>
    </div>

    <button className="cosmic-destination destination-1"
      onClick={() => openWorkspace('search')}>
      <span className="destination-orb"></span>
      <strong>Search the Sky</strong>
      <small>01 · DISCOVER</small>
    </button>

    <button className="cosmic-destination destination-2"
      onClick={() => openWorkspace('image')}>
      <span className="destination-orb"></span>
      <strong>Image Viewer</strong>
      <small>02 · VISUALIZE</small>
    </button>

    <button className="cosmic-destination destination-3"
      onClick={() => openWorkspace('timeline')}>
      <span className="destination-orb"></span>
      <strong>Timeline & Blink</strong>
      <small>03 · EXPLORE TIME</small>
    </button>

    <button className="cosmic-destination destination-4"
      onClick={() => openWorkspace('comparison')}>
      <span className="destination-orb"></span>
      <strong>Image Comparison</strong>
      <small>04 · ANALYZE</small>
    </button>

    <button className="cosmic-destination destination-5"
      onClick={() => openWorkspace('metadata')}>
      <span className="destination-orb"></span>
      <strong>Metadata & Provenance</strong>
      <small>05 · INVESTIGATE</small>
    </button>

    <button className="cosmic-destination destination-6"
      onClick={() => openWorkspace('candidates')}>
      <span className="destination-orb"></span>
      <strong>Candidate Review</strong>
      <small>06 · REVIEW</small>
    </button>
  </div>
</div>
)}



  {(activeWorkspace === 'search' || activeWorkspace === 'image') && (
  <div className="explorer-console">

    {activeWorkspace === 'search' && (
  <div className="search-panel">
      <div className="console-heading">
        <span>OBSERVATION SEARCH</span>
        <span className="console-indicator">ARCHIVE QUERY</span>
      </div>

      <h3>Define your search region</h3>
      <p className="console-description">
        Enter celestial coordinates to locate observations.
      </p>

      {targets.length > 0 && <><label htmlFor="target-preset-main">NASA target preset</label><select id="target-preset-main" value={selectedTarget} onChange={(e) => selectTarget(e.target.value)}><option value="">Custom coordinates</option>{targets.map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}</select></>}

      <label htmlFor="ra-input">Right Ascension (RA)</label>
<input
  id="ra-input"
  type="number"
  placeholder="e.g. 56.75"
  step="any"
  min="0"
  max="360"
  required
  value={ra}
  onChange={(e) => {
  setRa(e.target.value)
  setSelectedTarget('')
  setSearchMessage('')
  setIsSearching(false)
}}
/>

<label htmlFor="dec-input">Declination (Dec)</label>
<input
  id="dec-input"
  type="number"
  placeholder="e.g. 24.11"
  step="any"
  min="-90"
  max="90"
  required
  value={dec}
  onChange={(e) => {
  setDec(e.target.value)
  setSelectedTarget('')
  setSearchMessage('')
  setIsSearching(false)
}}
/>

{ra !== '' && (Number(ra) < 0 || Number(ra) >= 360) && (
  <p className="input-error">
    RA must be between 0° and less than 360°.
  </p>
)}

{dec !== '' && (Number(dec) < -90 || Number(dec) > 90) && (
  <p className="input-error">
    Dec must be between -90° and +90°.
  </p>
)}

{(ra === '' || dec === '') && (
  <p className="input-error">
    Enter both coordinates to continue.
  </p>
)}

      <label htmlFor="fov-select">Field of View</label>
      <select
        id="fov-select"
        value={fov}
            onChange={(e) => {
  setFov(e.target.value)
  setSearchMessage('')
  setIsSearching(false)
}}
>
  <option value="0.05">0.05 degrees</option>
  <option value="0.5">0.5 degrees — recommended for alignment</option>
  <option value="0.1">0.1 degrees</option>
  <option value="1">1 degree</option>
  <option value="2">2 degrees</option>
</select>

      <label htmlFor="release-select">Data Release</label>
<select
  id="release-select"
  value={dataRelease}
  onChange={(e) => {
  setDataRelease(e.target.value)
  setSearchMessage('')
  setIsSearching(false)
}}
>
  <option value="QR3">QR3 — Primary</option>
  <option value="QR2">QR2 — Fallback</option>
</select>

<label htmlFor="band-select">Spectral Band (optional)</label>
<select id="band-select" value={band} onChange={(e) => setBand(e.target.value)}>
  <option value="">All available bands</option>
  {['SPHEREx-D1', 'SPHEREx-D2', 'SPHEREx-D3', 'SPHEREx-D4', 'SPHEREx-D5', 'SPHEREx-D6'].map((value) => <option key={value} value={value}>{value}</option>)}
</select>

<label htmlFor="date-start">Start date (optional)</label>
<input id="date-start" type="date" value={dateStart} max={dateEnd || undefined} onChange={(e) => setDateStart(e.target.value)} />
<label htmlFor="date-end">End date (optional)</label>
<input id="date-end" type="date" value={dateEnd} min={dateStart || undefined} onChange={(e) => setDateEnd(e.target.value)} />

      <button
        type="button"
        disabled={!isValidCoordinates}
          onClick={handleSearch}
      >
        {isSearching ? 'Searching IRSA…' : 'Search Observations'}
      </button>
      {searchMessage && (
  <p className="search-status">{searchMessage}</p>
)}

      <p className="archive-note">
        Search requests use live NASA/IPAC IRSA data and validate coordinates before processing.
      </p>
    </div>
    )}



  </div>
  )}
</section>

<section className="closing-section" id="closing">
  <div className="closing-content">
    <p className="closing-eyebrow">SPHEREx • EXPLORING THE UNIVERSE</p>

    <h2>A New Perspective on the Universe.</h2>

    <p className="closing-description">
      Every wavelength reveals a different story.
      SPHEREx helps us explore the universe through infrared light.
    </p>

    <button
      className="explore-again-button"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
    >
      Explore Again
    </button>
  </div>
</section>

<footer className="site-footer">
  <div className="footer-brand">
    <h3>SPHEREx</h3>
    <p>Exploring the universe through infrared light.</p>
  </div>

  <div className="footer-links">
    <a href="#science">Science</a>
    <a href="#explorer">Explorer</a>
    <a href="#mission">Mission</a>
  </div>

  <p className="footer-credit">
    A NASA Astrophysics Mission
  </p>
</footer>

</main>
</>
)}

{activeWorkspace !== 'home' && (
  <main className="workspace-page">
    <button
      className="back-to-destinations"
      onClick={returnToDestinations}
    >
      ← Back to Destinations
    </button>

    <h1>
      {activeWorkspace === 'search' && 'Search the Sky'}
      {activeWorkspace === 'image' && 'Image Viewer'}
      {activeWorkspace === 'timeline' && 'Timeline & Blink'}
      {activeWorkspace === 'comparison' && 'Image Comparison'}
      {activeWorkspace === 'metadata' && 'Metadata & Provenance'}
      {activeWorkspace === 'candidates' && 'Candidate Review'}
    </h1>

        {activeWorkspace === 'image' && (
  <div className="observation-panel">

      <div className="observation-topbar">
        <span>OBSERVATION VIEWER</span>
        <span>{currentFrame ? `${currentFrame.product_id || currentFrame.observation_id} · ${currentFrame.obs_time || currentFrame.timestamp || 'time unavailable'}` : isSearching ? 'PROCESSING REAL DATA' : 'AWAITING QUERY'}</span>
      </div>

      <div className="viewer-toolbar">

  <div className="viewer-tabs">
  <button
    className={`viewer-tab ${activeViewerTab === 'Image' ? 'active' : ''}`}
    onClick={() => setActiveViewerTab('Image')}
  >
    Image
  </button>
</div>

  <div className="viewer-actions">
    <button onClick={() => openWorkspace('comparison')} disabled={!processingResult}>Compare</button>
    <a className="viewer-download" href={currentFrame?.preview_url || undefined} download={currentFrame ? `${currentFrame.product_id || 'spherex-frame'}.png` : undefined} aria-disabled={!currentFrame}>Download</a>
  </div>

</div>

{activeViewerTab === 'Image' && currentFrame?.preview_url ? (
      <div className="observation-image"><img src={viewerImageUrl} style={viewerImageStyle} alt={`SPHEREx observation ${currentFrame.product_id || ''}`} /><p>{currentFrame.band || 'Band unavailable'} · {currentFrame.collection || 'Collection unavailable'} · <a href={currentFrame.source_url} target="_blank" rel="noreferrer">IRSA product</a></p></div>
) : activeViewerTab === 'Image' && (

      <div className="observation-empty">
        <div className="viewer-orbit">
          <div className="viewer-core"></div>
          <div className="viewer-ring ring-one"></div>
          <div className="viewer-ring ring-two"></div>
        </div>

        <h3>Ready to explore the infrared sky?</h3>
<p>
  Enter celestial coordinates and search the NASA/IPAC archive.
  Available frames appear here after FITS validation and processing.
</p>
<span className="viewer-hint">AWAITING OBSERVATION DATA</span>
      </div>

)}


{activeViewerTab === 'Image' && (
<div className="display-controls">
  <div className="display-controls-heading">
    <div>
      <span>VISUALIZATION SETTINGS</span>
      <h3>Image Display</h3>
    </div>
    <span className="display-status">
  {currentFrame ? 'REAL PROCESSED FRAME' : isSearching ? 'PROCESSING' : 'AWAITING IMAGE'}
</span>
  </div>

  <div className="display-controls-body">
    <div className="display-control-group observation-picker">
      <label htmlFor="viewer-observation">OBSERVATION FRAME</label>
      <select id="viewer-observation" aria-label="Choose observation frame" value={currentFrameIndex} onChange={(event) => handleFrameChange(event.target.value)} disabled={!timelineFrames.length}>
        {timelineFrames.map((frame, index) => <option key={`${frame.product_id || frame.observation_id}-${index}`} value={index}>{frame.product_id || frame.observation_id} · {frame.obs_time || frame.timestamp || `Frame ${index + 1}`}</option>)}
      </select>
    </div>
    <div className="display-control-group">
      <label htmlFor="intensity-scaling">INTENSITY SCALING</label>
      <select
  id="intensity-scaling"
  value={intensityScaling}
  onChange={(e) => setIntensityScaling(e.target.value)}
>
  <option value="linear">Linear</option>
  <option value="log">Logarithmic</option>
  <option value="sqrt">Square Root</option>
  <option value="asinh">Asinh</option>
</select>
    </div>

    <div className="display-control-group">
      <label htmlFor="image-contrast">CONTRAST</label>
      <input
  id="image-contrast"
  type="range"
  min="0"
  max="100"
  value={contrast}
  onChange={(e) => setContrast(Number(e.target.value))}
/>
    </div>

    <div className="display-control-group">
      <label htmlFor="image-brightness">BRIGHTNESS</label>
      <input
  id="image-brightness"
  type="range"
  min="0"
  max="100"
  value={brightness}
  onChange={(e) => setBrightness(Number(e.target.value))}
/>
    </div>

    <label className="mask-toggle">
      <input
  type="checkbox"
  checked={showMask}
  onChange={(e) => setShowMask(e.target.checked)}
/>
      <span>Show data mask overlay</span>
    </label>
  </div>

  <div className="alignment-status">
    <span>WCS ALIGNMENT</span>
    <strong>
  {currentFrame ? 'Common WCS grid prepared by the science pipeline' : 'Waiting for image data'}
</strong>
  </div>
</div>
)}

      <div className="observation-footer">
        <span>DATA SOURCE: NASA / IPAC IRSA</span>
        <span>SCIENTIFIC DATA VIEW</span>
      </div>

    </div>
  )}

{activeWorkspace === 'candidates' && (
<div className="candidate-review">
  <div className="candidate-heading">
    <div>
      <span>SCIENTIFIC REVIEW</span>
      <h3>Candidate Investigation</h3>
      <p>Review and assess findings from loaded observations.</p>
    </div>
    <span className="candidate-status">
  {processingResult ? `${reviewCandidates.length} REVIEWABLE SIGNALS` : 'NO RESULTS'}
</span>
  </div>

  <div className="candidate-export-actions">
    <button type="button" onClick={() => downloadCandidateReport('csv')} disabled={!processingResult}>Export CSV</button>
    <button type="button" onClick={() => downloadCandidateReport('json')} disabled={!processingResult}>Export JSON</button>
  </div>

  <div className="review-workspace">
    <div className="review-sidebar">
      <span className="review-label">REVIEW QUEUE</span>
      <div className="queue-count">
        <strong>{filteredReviewCandidates.length}</strong>
        <span>Pending review</span>
      </div>
      <div className="queue-divider"></div>
      <div className="queue-filter">
  <span>STATUS</span>
  <select value={candidateFilter} onChange={(e) => setCandidateFilter(e.target.value)}>
  <option value="all">All reviewable signals</option>
  <option value="possible motion">Possible motion</option>
  <option value="possible brightness variability">Possible brightness variability</option>
</select>
</div>
    </div>

    <div className="review-main">
      {filteredReviewCandidates.length ? <><h4>Possible motion or brightness changes · human review required</h4>{ambiguousCandidateCount > 0 && <p>{ambiguousCandidateCount.toLocaleString()} ambiguous residual/source records were withheld from this review queue.</p>}<div className="candidate-table">{filteredReviewCandidates.map((candidate) => <article key={candidate.candidate_id}><strong>{candidate.classification || 'Unclassified change'}</strong><span>{candidate.ra_deg?.toFixed?.(5) ?? '—'}°, {candidate.dec_deg?.toFixed?.(5) ?? '—'}°</span><span>Significance: {candidate.max_abs_significance ?? candidate.flux_change_significance ?? 'not available'}</span><p>{candidate.scientific_caveat || 'Unverified candidate; not a confirmed discovery.'}</p></article>)}</div></> : <><div className="review-empty-symbol">+</div><h4>{reviewCandidates.length ? 'No signals match this status' : 'No reviewable signals detected'}</h4><p>{ambiguousCandidateCount ? `${ambiguousCandidateCount.toLocaleString()} ambiguous residual/source records remain in the full processing output.` : (apiError || searchMessage || 'Search the sky to begin investigating real observations.')}</p></>}
    </div>
  </div>

  <div className="review-footer">
    <span>REVIEW STATUS</span>
    <span>
  {searchMessage ? 'Search prepared — awaiting archive results' : 'Awaiting scientific results'}
</span>
  </div>
</div>
)}


{activeWorkspace === 'comparison' && (
  <div className="comparison-panel">

    <div className="comparison-heading">
      <div>
        <span>IMAGE ANALYSIS</span>
        <h3>Compare Observations</h3>
      </div>

      <span className="comparison-status">
        {currentComparison ? 'REAL PIPELINE DIFFERENCE AVAILABLE' : blockedComparison ? `COMPARISON BLOCKED: ${blockedComparison.reason || blockedComparison.explanation?.reason || blockedComparison.status}` : 'AWAITING VALID COMPARISON'}
      </span>
    </div>

    <div className="comparison-modes">
      <button
        className={comparisonMode === 'original' ? 'active' : ''}
        onClick={() => setComparisonMode('original')}
      >
        Original Frames
      </button>

      <button
        className={comparisonMode === 'difference' ? 'active' : ''}
        onClick={() => setComparisonMode('difference')}
      >
        Difference Image
      </button>

      <button
        className={comparisonMode === 'significance' ? 'active' : ''}
        onClick={() => setComparisonMode('significance')}
      >
        Significance Image
      </button>
    </div>

    <div className="comparison-pair-selectors">
      <label>IMAGE A<select aria-label="Choose first observation" value={comparisonAIndex} onChange={(event) => { setComparisonAIndex(Number(event.target.value)); setSelectedPairResult(null); setPairComparisonMessage('') }} disabled={timelineFrames.length < 2}>{timelineFrames.map((frame, index) => <option key={`a-${frame.product_id}-${index}`} value={index}>{frame.product_id} · {frame.obs_time || frame.timestamp}</option>)}</select></label>
      <label>IMAGE B<select aria-label="Choose second observation" value={comparisonBIndex} onChange={(event) => { setComparisonBIndex(Number(event.target.value)); setSelectedPairResult(null); setPairComparisonMessage('') }} disabled={timelineFrames.length < 2}>{timelineFrames.map((frame, index) => <option key={`b-${frame.product_id}-${index}`} value={index} disabled={index === comparisonAIndex}>{frame.product_id} · {frame.obs_time || frame.timestamp}</option>)}</select></label>
      <button type="button" onClick={runSelectedPairComparison} disabled={timelineFrames.length < 2 || comparisonAIndex === comparisonBIndex || isComparingSelectedPair}>{isComparingSelectedPair ? 'Comparing…' : 'Run comparison'}</button>
    </div>
    {pairComparisonMessage && <p className="comparison-pair-message" role="status">{pairComparisonMessage}</p>}

    {selectedComparison && <div className="metadata-grid comparison-science-summary">
      <div className="metadata-item"><span>ALIGNMENT SOURCES</span><strong>{selectedComparison.alignment?.matches ?? 'Not reported'}</strong></div>
      <div className="metadata-item"><span>PSF MATCHING</span><strong>{selectedComparison.psf_matching?.status || 'Not performed'}</strong></div>
      <div className="metadata-item"><span>NOISE COVARIANCE</span><strong>{selectedComparison.noise_covariance?.status || 'Not estimated'}</strong></div>
      <div className="metadata-item"><span>BLANK-SKY SAMPLES</span><strong>{selectedComparison.noise_covariance?.blank_sky_samples?.toLocaleString?.() || 'Not available'}</strong></div>
    </div>}

    {comparisonMode === 'original' && (
      <div className="comparison-workspace">

        <div className="comparison-view">
          <div className="comparison-view-label">
            <span>IMAGE A</span>
            <span>{timelineFrames[comparisonAIndex]?.product_id || 'Choose observation A'}</span>
          </div>

          {timelineFrames[comparisonAIndex]?.preview_url ? <img className="comparison-frame" src={timelineFrames[comparisonAIndex].preview_url} alt="First SPHEREx observation" /> : <div className="comparison-empty">
            <span>01</span>
            <p>First observation will appear here</p>
          </div>}
        </div>

        <div className="comparison-divider">
          <span>VS</span>
        </div>

        <div className="comparison-view">
          <div className="comparison-view-label">
            <span>IMAGE B</span>
            <span>{timelineFrames[comparisonBIndex]?.product_id || 'Choose observation B'}</span>
          </div>

          {timelineFrames[comparisonBIndex]?.preview_url ? <img className="comparison-frame" src={timelineFrames[comparisonBIndex].preview_url} alt="Second selected SPHEREx observation" /> : <div className="comparison-empty">
            <span>02</span>
            <p>Second observation will appear here</p>
          </div>}
        </div>

      </div>
    )}

    {comparisonMode === 'difference' && (
      <div className="comparison-view">
        <div className="comparison-view-label">
          <span>DIFFERENCE IMAGE</span>
          <span>Observation B − Observation A</span>
        </div>

        {selectedComparison?.difference_url ? <img className="comparison-frame" src={selectedComparison.difference_url} alt="Real SPHEREx difference image" /> : <div className="comparison-empty">
          <span>DIFF</span>
          <p>No scientifically valid difference product is available for the selected comparison.</p>
        </div>}
      </div>
    )}

    {comparisonMode === 'significance' && (
      <div className="comparison-view">
        <div className="comparison-view-label">
          <span>SIGNIFICANCE IMAGE</span>
          <span>Statistical significance</span>
        </div>

        {selectedComparison?.significance_url ? <img className="comparison-frame" src={selectedComparison.significance_url} alt="Real SPHEREx significance image" /> : <div className="comparison-empty">
          <span>SIG</span>
          <p>No significance product is available for the selected comparison.</p>
        </div>}
      </div>
    )}

    <div className="comparison-note">
      {comparisonMode === 'original'
        ? 'Compare two observation frames side by side.'
        : comparisonMode === 'difference'
        ? 'Difference images help highlight changes between observations. They are visual aids, not proof of a discovery.'
        : 'Significance images help assess the statistical strength of observed differences. They are not confirmation of a discovery.'}
    </div>

  </div>
)}



{activeWorkspace === 'metadata' && (
  <div className="metadata-workspace">

    {/* OBSERVATION METADATA */}
    <div className="metadata-panel">
      <div className="metadata-heading">
        <span>OBSERVATION METADATA</span>
        <span>
          {currentFrame ? 'REAL ARCHIVE OBSERVATION' : 'NO OBSERVATION LOADED'}
        </span>
      </div>

      <div className="metadata-grid">

        <div className="metadata-item">
          <span>RIGHT ASCENSION</span>
          <strong>{ra || '—'}</strong>
        </div>

        <div className="metadata-item">
          <span>DECLINATION</span>
          <strong>{dec || '—'}</strong>
        </div>

        <div className="metadata-item">
          <span>FIELD OF VIEW</span>
          <strong>{fov ? `${fov}°` : '—'}</strong>
        </div>

        <div className="metadata-item">
          <span>OBSERVATION DATE</span>
          <strong>{currentFrame?.obs_time || currentFrame?.timestamp || 'Not available from archive'}</strong>
        </div>

        <div className="metadata-item">
          <span>SPECTRAL BAND</span>
          <strong>{currentFrame?.band || 'Not available from archive'}</strong>
        </div>

        <div className="metadata-item">
          <span>DATA RELEASE</span>
          <strong>{currentFrame?.collection || dataRelease}</strong>
        </div>

        <div className="metadata-item">
          <span>OBSERVATION ID</span>
          <strong>{currentFrame?.product_id || currentFrame?.observation_id || 'Not available'}</strong>
        </div>

        <div className="metadata-item">
          <span>PROCESSING VERSION</span>
          <strong>{currentFrame?.finast || 'See processing report'}</strong>
        </div>

      </div>
    </div>

    {/* QUALITY INFORMATION */}
    <div className="metadata-panel">
      <div className="metadata-heading">
        <span>DATA QUALITY & FLAGS</span>
        <span>QUALITY INFORMATION</span>
      </div>

      <div className="metadata-grid">
        <div className="metadata-item">
          <span>QUALITY STATUS</span>
          <strong>{currentFrame ? 'Science pipeline processed' : 'No observation loaded'}</strong>
        </div>

        <div className="metadata-item">
          <span>MASK INFORMATION</span>
          {qualitySummary ? <div className="mask-quality-summary">
            <div className="mask-quality-stats">
              <div><strong>{Number(qualitySummary.valid_pixels || 0).toLocaleString()}</strong><span>usable pixels</span></div>
              <div><strong>{Number(qualitySummary.excluded_pixels ?? qualitySummary.invalid_variance ?? 0).toLocaleString()}</strong><span>excluded pixels</span></div>
              <div><strong>{Number(qualitySummary.uncovered || 0).toLocaleString()}</strong><span>outside image coverage</span></div>
            </div>
            {qualityFlags.length > 0 ? <details className="mask-flag-details">
              <summary>{qualityFlags.length} quality flags present</summary>
              <ul>{qualityFlags.map(([key, count]) => <li key={key}><span>{MASK_FLAG_LABELS[key] || key.replace(/^flag_/, '').replaceAll('_', ' ').toLowerCase()}</span><strong>{Number(count).toLocaleString()} pixels</strong></li>)}</ul>
            </details> : <p className="mask-no-flags">No nonzero instrument flags in this frame.</p>}
            <p className="mask-quality-note">Flagged pixels are excluded or treated cautiously during analysis; they do not mean the whole image is unusable.</p>
          </div> : <strong>Pixel mask summary is not available for this observation.</strong>}
        </div>

        <div className="metadata-item">
          <span>PROCESSING STATUS</span>
          <strong>{processingResult?.status || 'Not processed'}</strong>
        </div>

        <div className="metadata-item">
          <span>QUALITY WARNINGS</span>
          <strong>{processingResult?.warnings?.length ? processingResult.warnings.join(' ') : 'No pipeline warnings reported'}</strong>
        </div>
      </div>
    </div>

    {/* DATA PROVENANCE */}
    <div className="provenance-panel">
      <div className="provenance-title">
        <span>DATA PROVENANCE</span>
        <span>TRANSPARENCY & TRACEABILITY</span>
      </div>

      <div className="provenance-content">

        <div className="provenance-source">
          <span>ARCHIVE SOURCE</span>
          <strong>NASA / IPAC Infrared Science Archive (IRSA)</strong>
        </div>

        <div className="provenance-release">
          <span>DATA COLLECTION</span>
          <strong>{currentFrame?.collection || dataRelease}</strong>
        </div>

        <div className="provenance-source">
          <span>PROCESSING PIPELINE</span>
          <strong>SPHEREx Explorer Science Processing Pipeline</strong>
        </div>

        <div className="provenance-source">
          <span>DATA ORIGIN</span>
          <strong>SPHEREx observations</strong>
        </div>

        <div className="provenance-note">
          {currentFrame ? `Product ${currentFrame.product_id || currentFrame.observation_id} was retrieved from the IRSA archive. The linked product URL and science quality warnings are shown with the selected observation.` : 'Search for real archive observations to view source records, processing history, product IDs, and quality information.'}
        </div>

      </div>
    </div>

  </div>
)}



    {activeWorkspace === 'timeline' && (
  <div className="timeline-panel">

    <div className="timeline-heading">
      <div>
        <span>OBSERVATION HISTORY</span>
        <h3>Time Across the Sky</h3>
      </div>

      <span className="timeline-status">
        {isSearching ? 'PROCESSING REAL DATA' : timelineFrames.length ? `${timelineFrames.length} REAL FRAMES` : 'AWAITING OBSERVATION DATA'}
      </span>
    </div>

    {/* IMAGE VIEWER */}
    <div className="timeline-image-viewer">
      <div className="timeline-image-topbar">
        <span>SELECTED OBSERVATION</span>
        <span>{currentFrame ? `${currentFrame.product_id || currentFrame.observation_id} · ${currentFrame.collection || ''}` : 'NO FRAME LOADED'}</span>
      </div>

      {currentFrame?.preview_url ? <div className="timeline-image-real"><img src={currentFrame.preview_url} alt={`SPHEREx image for ${currentFrame.product_id || 'selected observation'}`} /></div> : <div className="timeline-image-empty">
        <span>01</span>
        <h3>No observation frame available</h3>
        <p>
          Search results containing processed SPHEREx images
          will appear here.
        </p>
      </div>}
    </div>


{/* TIMESTAMP AND FRAME INFORMATION */}
<div className="timeline-frame-info">
  <div>
    <span>OBSERVATION DATE</span>
    <strong>
      {currentFrame
        ? currentFrame.timestamp || currentFrame.obs_time || currentFrame.observationDate ||
          currentFrame.observation_date ||
          currentFrame.date ||
          'Date unavailable'
        : 'Awaiting data'}
    </strong>
  </div>

  <div>
    <span>FRAME</span>
    <strong>
      {timelineFrames.length > 0
        ? `${currentFrameIndex + 1} / ${timelineFrames.length}`
        : '0 / 0'}
    </strong>
  </div>

  <div>
    <span>PLAYBACK STATUS</span>
    <strong>
      {timelineFrames.length === 0
        ? 'Waiting for frames'
        : isTimelinePlaying
          ? 'Playing'
          : timelineFrames.length < 2
            ? 'One frame available'
            : 'Paused'}
    </strong>
  </div>
</div>



{/* PLAYBACK CONTROLS */}
<div className="timeline-controls">

  <button
    onClick={handlePreviousFrame}
    disabled={timelineFrames.length === 0 || currentFrameIndex === 0}
  >
    ← Previous
  </button>

  <button
    onClick={handleTimelinePlay}
    disabled={timelineFrames.length < 2}
  >
    {isTimelinePlaying ? 'Pause' : 'Play'}
  </button>

  <button
    onClick={handleNextFrame}
    disabled={
      timelineFrames.length === 0 ||
      currentFrameIndex === timelineFrames.length - 1
    }
  >
    Next →
  </button>

  <div className="timeline-speed">
    <label htmlFor="timeline-speed-select">
      PLAYBACK SPEED
    </label>

    <select
      id="timeline-speed-select"
      value={timelineSpeed}
      onChange={(e) => setTimelineSpeed(e.target.value)}
    >
      <option value="0.5x">0.5x</option>
      <option value="1x">1x</option>
      <option value="2x">2x</option>
      <option value="4x">4x</option>
    </select>
  </div>

</div>

{/* FRAME SLIDER */}
<div className="timeline-slider-section">
  <div className="timeline-slider-label">
    <span>FRAME POSITION</span>
    <span>
      {timelineFrames.length > 0
        ? `${currentFrameIndex + 1} / ${timelineFrames.length}`
        : '0 / 0'}
    </span>
  </div>

  <input
    type="range"
    min="0"
    max={Math.max(0, timelineFrames.length - 1)}
    value={currentFrameIndex}
    disabled={timelineFrames.length === 0}
    onChange={(e) => handleFrameChange(e.target.value)}
    aria-label="Observation frame position"
  />
</div>


    {/* OBSERVATION TIMELINE */}
    <div className="timeline-history">
      <div className="timeline-history-heading">
        <span>OBSERVATION TIMELINE</span>
        <span>CHRONOLOGICAL ORDER</span>
      </div>

      <div className="timeline-track">
        <div className="timeline-line"></div>
        <div className="timeline-empty-marker"></div>
      </div>

      <p className="timeline-empty-text">
        {apiError ? apiError : searchMessage
          ? searchMessage
          : 'Search a region of the sky to explore its SPHEREx observation history.'}
      </p>
    </div>

    <div className="timeline-note">
      Blink playback requires at least two real, processed observation
      frames. Image intensity scaling will remain consistent across
      observation epochs.
    </div>

  </div>
)}


    {activeWorkspace === 'search' && (
      <section className="search-workspace">

        <div className="search-panel">
      <div className="console-heading">
        <span>OBSERVATION SEARCH</span>
        <span className="console-indicator">ARCHIVE QUERY</span>
      </div>

      <h3>Define your search region</h3>
      <p className="console-description">
        Enter celestial coordinates to locate observations.
      </p>

      {targets.length > 0 && <><label htmlFor="target-preset-secondary">NASA target preset</label><select id="target-preset-secondary" value={selectedTarget} onChange={(e) => selectTarget(e.target.value)}><option value="">Custom coordinates</option>{targets.map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}</select></>}

      <label htmlFor="ra-input">Right Ascension (RA)</label>
<input
  id="ra-input"
  type="number"
  placeholder="e.g. 56.75"
  step="any"
  min="0"
  max="360"
  required
  value={ra}
  onChange={(e) => {
  setRa(e.target.value)
  setSelectedTarget('')
  setSearchMessage('')
  setIsSearching(false)
}}
/>

<label htmlFor="dec-input">Declination (Dec)</label>
<input
  id="dec-input"
  type="number"
  placeholder="e.g. 24.11"
  step="any"
  min="-90"
  max="90"
  required
  value={dec}
  onChange={(e) => {
  setDec(e.target.value)
  setSelectedTarget('')
  setSearchMessage('')
  setIsSearching(false)
}}
/>

{ra !== '' && (Number(ra) < 0 || Number(ra) >= 360) && (
  <p className="input-error">
    RA must be between 0° and less than 360°.
  </p>
)}

{dec !== '' && (Number(dec) < -90 || Number(dec) > 90) && (
  <p className="input-error">
    Dec must be between -90° and +90°.
  </p>
)}

{(ra === '' || dec === '') && (
  <p className="input-error">
    Enter both coordinates to continue.
  </p>
)}

      <label htmlFor="fov-select">Field of View</label>
      <select
        id="fov-select"
        value={fov}
            onChange={(e) => {
  setFov(e.target.value)
  setSearchMessage('')
  setIsSearching(false)
}}
>
  <option value="0.05">0.05 degrees</option>
  <option value="0.5">0.5 degrees — recommended for alignment</option>
  <option value="0.1">0.1 degrees</option>
  <option value="1">1 degree</option>
  <option value="2">2 degrees</option>
</select>

      <label htmlFor="release-select">Data Release</label>
<select
  id="release-select"
  value={dataRelease}
  onChange={(e) => {
  setDataRelease(e.target.value)
  setSearchMessage('')
  setIsSearching(false)
}}
>
  <option value="QR3">QR3 — Primary</option>
  <option value="QR2">QR2 — Fallback</option>
</select>

<label htmlFor="band-select">Spectral Band (optional)</label>
<select id="band-select" value={band} onChange={(e) => setBand(e.target.value)}>
  <option value="">All available bands</option>
  {['SPHEREx-D1', 'SPHEREx-D2', 'SPHEREx-D3', 'SPHEREx-D4', 'SPHEREx-D5', 'SPHEREx-D6'].map((value) => <option key={value} value={value}>{value}</option>)}
</select>

<label htmlFor="date-start">Start date (optional)</label>
<input id="date-start" type="date" value={dateStart} max={dateEnd || undefined} onChange={(e) => setDateStart(e.target.value)} />
<label htmlFor="date-end">End date (optional)</label>
<input id="date-end" type="date" value={dateEnd} min={dateStart || undefined} onChange={(e) => setDateEnd(e.target.value)} />

      <button
        type="button"
        disabled={!isValidCoordinates || isSearching}
          onClick={handleSearch}
      >
        {isSearching ? 'Searching IRSA…' : 'Search Observations'}
      </button>
      {searchMessage && (
  <p className="search-status">{searchMessage}</p>
)}
{apiError && <p className="input-error">{apiError}</p>}
{observations.length > 0 && <div className="archive-results"><h4>Live archive results ({observations.length})</h4>{observations.slice(0, 12).map((observation) => <article key={`${observation.observation_id}-${observation.band}`}><strong>{observation.obs_time || 'Observation time unavailable'}</strong><span>{observation.product_id || observation.observation_id} · {observation.release || observation.collection || 'Release unavailable'} · {observation.band || 'Band unavailable'} · Quality: {observation.quality_summary ? 'metadata available' : 'not supplied'}</span></article>)}</div>}

      <p className="archive-note">Searches NASA/IPAC IRSA. Frames appear only after real archive products pass FITS validation and science processing.</p>
    </div>

      </section>
    )}

  </main>
)}

</div>
)
}

export default App
