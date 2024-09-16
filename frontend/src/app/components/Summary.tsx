'use client'

import { useState, useEffect } from 'react';
import styles from "@/styles/Report.module.css"



interface SummaryData {
    headline : string;
    body : string;
}

export default function Report() {
    const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiUrl = process.env.NEXT_PUBLIC_REPORT_GENERATOR_URL;

    useEffect(() => {
        const fetchSummary = async () => {
          try {
            const response = await fetch(`${apiUrl}/summary`);
            if (!response.ok) {
              throw new Error('Failed to fetch summary');
            }
            const data = await response.json();
            setSummaryData(data)
          } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
          } finally {
            setIsLoading(false);
          }
        };
        fetchSummary();
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
            <p>Loading Summary...</p>
        </div>)
    }
    return (
      <div className={styles.container}>
        <div>
            <div className={styles.titleContainer}>
                <h2 className={styles.headline}>{summaryData?.headline}</h2>
            </div>
            <div>
                <p className={styles.reportBody}>{summaryData?.body}</p>
            </div>
        </div>
      </div>
    )
  }