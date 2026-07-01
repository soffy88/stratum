/**
 * /chat — 对话 Page(REQ-003)。
 *
 * 让 Wiki 能在浏览器里跟 AII 对话。每个回答暴露:
 *   - mode(grounded / chitchat / no_knowledge)
 *   - epistemic_confidence + basis(可信度一等公民)
 *   - citations(可核查依据)
 *   - disclaimer(金融场景必有)
 */
import { ChatPage } from '@/aii/components/chat/ChatPage';

export default function Page() {
  return <ChatPage />;
}
