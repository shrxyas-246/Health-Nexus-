export default function ChapterBar({ chapter, links, activeId }) {
  const onClick = (e, id) => {
    e.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }
  return (
    <div className="chapter">
      <div className="chapter-in">
        <span className="chapter-title">{chapter}</span>
        <div className="chapter-links">
          {links.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              className={activeId === l.id ? 'active' : ''}
              onClick={(e) => onClick(e, l.id)}
            >
              {l.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
