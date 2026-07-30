import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn("prose prose-sm dark:prose-invert max-w-none break-words", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
        table: ({ children }) => (
          <div className="overflow-x-auto my-2 rounded-lg border border-border">
            <table className="min-w-full divide-y divide-border border-collapse">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-muted/50">{children}</thead>,
        th: ({ children }) => (
          <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider border-b border-border">
            {children}
          </th>
        ),
        td: ({ children }) => <td className="px-3 py-2 text-xs border-b border-border">{children}</td>,
        tr: ({ children }) => <tr className="hover:bg-muted/30 transition-colors">{children}</tr>,
        ul: ({ children }) => <ul className="list-disc pl-4 space-y-1 my-2">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-4 space-y-1 my-2">{children}</ol>,
        li: ({ children }) => <li className="text-xs leading-relaxed">{children}</li>,
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-bold text-primary">{children}</strong>,
      }}
    >
      {content}
    </ReactMarkdown>
    </div>
  );
}
