import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Button } from "@/components/ui/button"
import { Copy, Check } from "lucide-react"

interface CodeBlockProps {
  node?: any
  inline?: boolean
  className?: string
  children?: React.ReactNode
}

const CodeBlock: React.FC<CodeBlockProps> = ({ inline = false, className, children }) => {
  const match = /language-(\w+)/.exec(className || '')
  const language = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')

  const [isCopied, setIsCopied] = useState(false)

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code)
    setIsCopied(true)
    setTimeout(() => setIsCopied(false), 2000)
  }

  return !inline && language === 'python' ? (
    <div className="relative">
      <SyntaxHighlighter
        children={code}
        style={vscDarkPlus}
        language={language}
        PreTag="div"
        className="rounded-lg"
      />
      <Button
        variant="outline"
        size="icon"
        className="absolute top-2 right-2"
        onClick={copyToClipboard}
      >
        {isCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  ) : (
    <code className={className}>
      {children}
    </code>
  )
}

interface MarkdownRendererProps {
  markdownText: string
}

export function MarkdownRenderer({ markdownText } : MarkdownRendererProps)  {
  // Custom components for collapsible sections
  const Details: React.FC<React.HTMLAttributes<HTMLDetailsElement>> = ({ children, ...props }) => (
    <details className="group border rounded-md my-3 p-3 bg-muted/30" {...props}>
      {children}
    </details>
  )

  const Summary: React.FC<React.HTMLAttributes<HTMLElement>> = ({ children, ...props }) => (
    <summary
      className="cursor-pointer list-none font-medium flex items-center gap-2 marker:hidden [&::-webkit-details-marker]:hidden focus:outline-none focus:ring-2 focus:ring-ring rounded-sm select-none"
      {...props}
    >
      <span className="transition-transform group-open:rotate-90 inline-block">▶</span>
      {children}
    </summary>
  )

  return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          code: CodeBlock,
          details: ({node, ...props}) => <Details {...props} />,
          summary: ({node, ...props}) => <Summary {...props} />
        }}
      >
        {markdownText}
      </ReactMarkdown>
  )
}