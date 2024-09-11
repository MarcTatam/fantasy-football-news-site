from football_reports.models.report import Report
from google.cloud.firestore import Client

class FirestoreClient:
    def __init__(self) -> None:
        self.client = Client()

    def add_to_db(self, report:Report, gw_id:int, complete:bool):
        collection = self.client.collection("reports")
        if collection.document(str(gw_id)).get().exists:
            collection.document(str(gw_id)).update({
            "headline" : report.headline,
            "body" : report.body,
            "complete" : complete
        }
            )
        collection.add(document_id=str(gw_id), document_data={
            "headline" : report.headline,
            "body" : report.body,
            "complete" : complete
        })

    def get_from_db(self, gw_id:int)->Report:
        collection = self.client.collection("reports")
        doc = collection.document(str(gw_id)).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict.get("complete"):
                return Report.model_validate(doc_dict)
            