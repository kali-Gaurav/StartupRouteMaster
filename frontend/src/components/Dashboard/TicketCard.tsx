/**
 * Ticket Card Component
 * Displays a single ticket with download/print options
 */

import { Link } from "react-router-dom";
import { Ticket as TicketIcon, Download, Print } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TicketCardProps {
  id: string;
  originName: string;
  destName: string;
  travelDate?: string;
  reference: string;
  onDownload?: () => void;
  onPrint?: () => void;
}

export function TicketCard({
  id,
  originName,
  destName,
  travelDate,
  reference,
  onDownload = () => console.log("Download:", id),
  onPrint = () => console.log("Print:", id),
}: TicketCardProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 hover:border-primary/40 transition-all hover:shadow-md">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <p className="font-bold text-sm">
            {originName} → {destName}
          </p>
          <p className="text-xs text-muted-foreground font-medium mt-1">
            {travelDate ? new Date(travelDate + "T12:00:00").toLocaleDateString("en-IN") : "—"}
          </p>
        </div>
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <TicketIcon className="w-5 h-5 text-primary" />
        </div>
      </div>
      <p className="text-xs font-mono text-muted-foreground break-all mb-3 bg-muted/30 p-2 rounded">
        Ref: {reference}
      </p>
      <div className="flex gap-2">
        <Link
          to={`/ticket/${encodeURIComponent(id)}`}
          className="flex-1 px-3 py-2 rounded-lg bg-primary/10 text-primary text-xs font-bold hover:bg-primary/20 transition-colors text-center"
        >
          View
        </Link>
        <Button
          onClick={onDownload}
          variant="outline"
          size="sm"
          className="px-2"
          title="Download ticket"
        >
          <Download className="w-4 h-4" />
        </Button>
        <Button
          onClick={onPrint}
          variant="outline"
          size="sm"
          className="px-2"
          title="Print ticket"
        >
          <Print className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

export default TicketCard;
