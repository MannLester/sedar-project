import { useEngineRoom } from '../../context/engineRoomStore'

export function Banners() {
  const { problem, queue, discardQueued } = useEngineRoom()
  const rejected = queue.filter((item) => item.error)

  return (
    <>
      {problem && (
        <div role="alert" className="mb-3 rounded-[10px] border border-amber-300 bg-amber-50 px-5 py-3 text-sm text-amber-900">
          {problem}{' '}
          <a className="font-bold underline" href="/web/login" target="_top">Log in</a>
        </div>
      )}
      {rejected.map((item) => (
        <div key={item.client_id} role="alert" className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-red-300 bg-red-50 px-5 py-3 text-sm text-red-900">
          <span><strong>{item.label}</strong> was not accepted: {item.error}</span>
          <button type="button" className="button button-secondary" onClick={() => discardQueued(item.client_id)}>Discard</button>
        </div>
      ))}
    </>
  )
}
