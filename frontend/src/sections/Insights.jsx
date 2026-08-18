import { useUI } from '../context/UIContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { shortDate } from '../lib/format.js'
import { Loading, ErrorState, Empty } from '../components/States.jsx'

const THUMBS = ['th-lab', 'th-med', 'th-well']
const firstTag = (tags) => (tags || '').split(',')[0]?.trim() || 'Health'

export default function Insights() {
  const { modal, toast } = useUI()
  const { data, loading, error, reload, setData } = useResource(() => api.posts({ limit: 8 }), [])

  const open = (post) => modal(
    post.title,
    [
      `${post.author_name}${post.author_specialization ? ` · ${post.author_specialization}` : ''}`,
      `${shortDate(post.published_at)} · ${post.read_minutes} min read`,
      '',
      post.body
    ].join('\n')
  )

  const like = async (post, e) => {
    e.stopPropagation()
    try {
      const updated = await api.likePost(post.id)
      setData((posts) => posts.map((p) => (p.id === post.id ? updated : p)))
    } catch {
      toast('Could not register that')
    }
  }

  if (loading) {
    return <section id="insights" data-chapter="Care & Insights" data-nav="Insights"><Loading label="Loading articles…" /></section>
  }
  if (error) {
    return <section id="insights" data-chapter="Care & Insights" data-nav="Insights"><ErrorState error={error} onRetry={reload} /></section>
  }

  const [featured, ...rest] = data || []

  return (
    <section id="insights" data-chapter="Care & Insights" data-nav="Insights">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Health updates & insights</div>
          <h2>Written by doctors on HealthNexus.</h2>
        </div>
      </div>

      {!featured && <Empty title="No articles published yet" />}

      {featured && (
        <div className="feature reveal">
          <div className="thumb th-card">
            <svg className="deco" viewBox="0 0 400 230" preserveAspectRatio="none">
              <path
                d="M0 150 L60 150 L80 110 L100 175 L120 90 L145 150 L400 150"
                fill="none" stroke="rgba(255,255,255,.5)" strokeWidth="3" strokeLinejoin="round"
              />
            </svg>
            <span className="cat">Featured · {firstTag(featured.tags)}</span>
          </div>
          <div>
            <h2>{featured.title}</h2>
            <p className="muted">{featured.excerpt}</p>
            <div className="meta3" style={{ marginTop: 10 }}>
              {featured.author_name} · {featured.read_minutes} min read · {featured.like_count} likes
            </div>
            <a className="view" href="#insights" onClick={(e) => { e.preventDefault(); open(featured) }}>
              Read article →
            </a>
          </div>
        </div>
      )}

      {rest.length > 0 && (
        <div className="stories reveal">
          {rest.slice(0, 3).map((post, i) => (
            <article className="story" key={post.id} onClick={() => open(post)} role="button" tabIndex={0}
                     onKeyDown={(e) => e.key === 'Enter' && open(post)}>
              <div className={`thumb ${THUMBS[i % THUMBS.length]}`}>
                <span className="cat">{firstTag(post.tags)}</span>
              </div>
              <div className="body">
                <h3>{post.title}</h3>
                <div className="meta3">
                  {post.read_minutes} min read · {post.author_name}
                  <button className="like" onClick={(e) => like(post, e)}>♥ {post.like_count}</button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
