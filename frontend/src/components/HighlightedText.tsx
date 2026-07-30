import React from "react";

interface HighlightedTextProps {
  text: string;
  highlight: string;
}

/**
 * [47.1] Component to highlight matching substrings in station names.
 */
export const HighlightedText = ({ text, highlight }: HighlightedTextProps) => {
  if (!highlight.trim()) {
    return <span>{text}</span>;
  }

  const regex = new RegExp(`(${highlight})`, "gi");
  const parts = text.split(regex);

  return (
    <span>
      {parts.map((part, i) => (
        regex.test(part) ? (
          <span key={i} className="font-black text-blue-600 underline underline-offset-2">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      ))}
    </span>
  );
};
