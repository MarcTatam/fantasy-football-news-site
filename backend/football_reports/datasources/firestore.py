from ..models.report import Report
from ..models.response import ReportResponse
from google.cloud.firestore import Client

class FirestoreClient:
    def __init__(self) -> None:
        self.client = Client()

    def add_report_to_db(self, report:Report, gw_id:int, complete:bool):
        collection = self.client.collection("reports")
        if collection.document(str(gw_id)).get().exists:
            collection.document(str(gw_id)).update({
                "headline" : report.headline,
                "body" : report.body,
                "complete" : complete
                }
            )
            return
        collection.add(document_id=str(gw_id), document_data={
            "headline" : report.headline,
            "body" : report.body,
            "complete" : complete
        })

    def get_report_from_db(self, gw_id:int)->Report:
        collection = self.client.collection("reports")
        doc = collection.document(str(gw_id)).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict.get("complete"):
                return Report.model_validate(doc_dict)
            
    def get_all_reports_from_db(self)->list[ReportResponse]:
        collection = self.client.collection("reports")
        docs = collection.list_documents()
        out = []
        for item in docs:
            temp = item.get().to_dict()
            temp_report = Report.model_validate(temp)
            out.append(ReportResponse(headline=temp_report.headline, body=temp_report.body, complete=temp.get("complete"), gw_id=item.id))
        return out
        