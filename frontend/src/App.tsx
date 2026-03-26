import { Layout } from './components/Layout'
import { GraphViewer } from './components/GraphViewer'
import { ChatPanel } from './components/ChatPanel'

export default function App() {
  return <Layout left={<GraphViewer />} right={<ChatPanel />} />
}
