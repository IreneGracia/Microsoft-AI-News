'use client'

import CardsBlock from '@/components/chat/CardsBlock'
import { FONTS } from '@/constants/fonts'
import type { ChatMessage, NewsCard, Palette } from '@/types'

interface Props {
  msg: ChatMessage
  palette: Palette
  displayFont: string
  compact: boolean
  onAction: (kind: string, card: NewsCard) => void
  onActionChip: (a: { id: string; label: string; icon: string }) => void
  onFollowup: (f: string) => void
  savedIds?: Set<string>
  onToggleSave?: (card: NewsCard) => void
}

export default function Message({ msg, palette, displayFont, compact, onAction, onActionChip, onFollowup, savedIds, onToggleSave }: Props) {
  const isUser = msg.role === 'user'

  if (msg.briefing) {
    return (
      <div className="msg msg-ai briefing-msg">
        <div className="briefing-header" style={{ color: palette.muted }}>
          {msg.briefing.header}
        </div>
        <div className="briefing-greeting" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
          {msg.briefing.greeting}
        </div>
        <div className="briefing-subtitle" style={{ color: palette.muted }}>
          {msg.briefing.subtitle}
        </div>
        {msg.cards && (
          <CardsBlock
            cards={msg.cards} palette={palette}
            followups={msg.briefing.followups}
            savedIds={savedIds} onToggleSave={onToggleSave}
            onAction={onAction} onActionChip={onActionChip} onFollowup={onFollowup}
          />
        )}
      </div>
    )
  }

  return (
    <div className={`msg ${isUser ? 'msg-user' : 'msg-ai'} ${compact ? 'msg-compact' : ''}`}>
      {!isUser && (
        <div className="msg-byline" style={{ fontFamily: FONTS[displayFont], color: palette.muted }}>
          MAI
        </div>
      )}
      {msg.thinking ? (
        <div className="bubble bubble-ai" style={{ background: palette.bubbleAi, color: palette.ink, borderColor: 'rgba(0,0,0,0.06)' }}>
          <span className="thinking"><span className="dot" /><span className="dot" /><span className="dot" /></span>
        </div>
      ) : (
        <>
          {msg.content && (
            <div
              className={`bubble ${isUser ? 'bubble-user' : 'bubble-ai'}`}
              style={isUser
                ? { background: palette.bubbleUser, color: palette.bubbleUserInk }
                : { background: palette.bubbleAi, color: palette.ink, borderColor: 'rgba(0,0,0,0.06)' }}
            >
              <span className="bubble-text">{msg.content}</span>
            </div>
          )}
          {msg.cards && (
            <CardsBlock cards={msg.cards} palette={palette}
              savedIds={savedIds} onToggleSave={onToggleSave}
              onAction={onAction} onActionChip={onActionChip} onFollowup={onFollowup} />
          )}
        </>
      )}
    </div>
  )
}
