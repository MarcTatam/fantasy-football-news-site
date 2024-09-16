import Image from "next/image";
import "./page.module.css";
import LeagueGraph from "./components/LeagueGraph";
import Button from "./components/Button";

export default function Home() {
  return (
    <div>
      <LeagueGraph/>
      <Button linkAdress="/report" text="View the reports!"/>
      <Button linkAdress="/summary" text="View a season summary report!"/>
    </div>
  );
}
