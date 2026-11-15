import { useMemo } from 'react'
import { DefaultChatTransport } from 'ai'

import { getAccessToken } from '@/lib/api'
import { env } from '@/lib/env'
import { ApiError } from '@/lib/http'

export function useChatTransport(threadId: string) {
  return useMemo(
    () =>
      new DefaultChatTransport({
        api: `${env.apiBaseUrl}/chat/stream`,
        headers: async (): Promise<Record<string, string>> => {
          const token = await getAccessToken()
          return token ? { Authorization: `Bearer ${token}` } : {}
        },
        prepareSendMessagesRequest: ({ messages }) => ({
          body: {
            threadId,
            messages: messages
              .map((message) => ({
                ...message,
                parts: message.parts.filter(
                  (part) => part.type === 'text' || part.type === 'data-citation',
                ),
              }))
              .filter((message) => message.parts.length > 0),
          },
        }),
        fetch: async (input, init) => {
          const response = await fetch(input, init)

          if (!response.ok) {
            const detail: unknown = await response.json().catch(() => null)
            const message =
              detail !== null && typeof detail === 'object' &&
              'detail' in detail && typeof detail.detail === 'string'
                ? detail.detail
                : `Request failed (${response.status})`
            throw new ApiError(message, { status: response.status, detail })
          }

          return response
        },
      }),
    [threadId],
  )
}
