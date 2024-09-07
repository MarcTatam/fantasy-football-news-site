'use client'

import { useState, useEffect } from 'react';
import styles from "@/styles/Report.module.css"

interface ReportData {
    headline : string;
    body : string;
}

export default function Report() {
    const [reportData, setReportData] = useState<ReportData | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => {
        const fetchReport = async () => {
          try {
            const response = await fetch('https://europe-west9-football-value-app.cloudfunctions.net/report-generator-2/');
            if (!response.ok) {
              throw new Error('Failed to fetch users');
            }
            const data = await response.json();
            setReportData(data)
            setIsLoading(false);
          } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
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