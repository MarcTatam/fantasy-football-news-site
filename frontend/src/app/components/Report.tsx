'use client'

import { useState, useEffect } from 'react';
import styles from "@/styles/Report.module.css"

const apiUrl = process.env.NEXT_PUBLIC_REPORT_GENERATOR_URL;

interface ReportData {
    headline : string;
    body : string;
}

interface ReportProps {
  gw_id?:Number;
}

export default function Report(reportProps:ReportProps) {
    const [reportData, setReportData] = useState<ReportData | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => {
        const fetchReport = async () => {
          try {
            const response = await fetch(reportProps.gw_id ? `${apiUrl}/report/${reportProps.gw_id}`: `${apiUrl}`);
            if (!response.ok) {
              throw new Error('Failed to fetch report');
            }
            const data = await response.json();
            setReportData(data)
          } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
          } finally {
            setIsLoading(false);
          }
        };
        fetchReport();
    },[])
    if (error){
        return (
        <div className={styles.container}>
            <p>An error occurred {error}</p>
        </div>
        )
    }
    if (isLoading){
        return (<div className={styles.container}>
            <p>Loading Report...</p>
        </div>)
    }
    return (
      <div className={styles.container}>
        <div>
            <div className={styles.titleContainer}>
                <h2 className={styles.headline}>{reportData?.headline}</h2>
            </div>
            <div>
                <p className={styles.reportBody}>{reportData?.body}</p>
            </div>
        </div>
      </div>
    )
  }