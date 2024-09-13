'use client'
import Report from "@/components/Report";
import { useParams } from 'next/navigation'

export default function ReportPage() {
  const params = useParams<{ id: string; }>()
  return (
    <Report gw_id={Number(params.id)}></Report>
  );
}
