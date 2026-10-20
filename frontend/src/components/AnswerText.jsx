/**
 * Minimal, safe formatter for model answers: paragraphs, bullet/numbered
 * lists, **bold**, and [n] citation markers. Builds React elements directly
 * (no dangerouslySetInnerHTML), so model output can never inject HTML.
 */
function inline(text, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d{1,2}\])/g).filter(Boolean)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={key}>{part.slice(2, -2)}</strong>
    const cite = part.match(/^\[(\d{1,2})\]$/)
    if (cite)
      return (
        <sup key={key} className="mx-0.5 rounded bg-brand-50 px-1 text-[10px] font-semibold text-brand-600">
          {cite[1]}
        </sup>
      )
    return <span key={key}>{part}</span>
  })
}

export default function AnswerText({ text, streaming }) {
  const blocks = []
  let list = null
  text.split('\n').forEach((raw, idx) => {
    const line = raw.trimEnd()
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/)
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (bullet || numbered) {
      const type = bullet ? 'ul' : 'ol'
      if (!list || list.type !== type) {
        list = { type, items: [] }
        blocks.push(list)
      }
      list.items.push((bullet || numbered)[1])
      return
    }
    list = null
    if (line.trim()) blocks.push({ type: 'p', text: line, idx })
  })

  return (
    <div className="prose-answer text-[15px] leading-relaxed text-slate-800">
      {blocks.map((b, i) => {
        const isLast = i === blocks.length - 1
        const cursor = streaming && isLast ? <Cursor /> : null
        if (b.type === 'p')
          return (
            <p key={i}>
              {inline(b.text, `p${i}`)}
              {cursor}
            </p>
          )
        const Tag = b.type
        return (
          <Tag key={i}>
            {b.items.map((it, j) => (
              <li key={j}>
                {inline(it, `l${i}-${j}`)}
                {isLast && j === b.items.length - 1 ? cursor : null}
              </li>
            ))}
          </Tag>
        )
      })}
      {streaming && blocks.length === 0 && <Cursor />}
    </div>
  )
}

function Cursor() {
  return <span className="ml-0.5 inline-block h-[1.1em] w-[2px] translate-y-[3px] animate-blink bg-brand-500" aria-hidden="true" />
}
