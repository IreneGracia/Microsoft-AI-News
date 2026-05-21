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
}

export default function Message({ msg, palette, displayFont, compact, onAction, onActionChip, onFollowup }: Props) {
  const isUser = msg.role === 'user'
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
              onAction={onAction} onActionChip={onActionChip} onFollowup={onFollowup} />
          )}
        </>
      )}
    </div>
  )
}
