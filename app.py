import streamlit as st
from azure.storage.blob import BlobServiceClient
import os
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
import requests
import pandas as pd

# ---------------------------
# Application Insights ログ設定
# ---------------------------

#Application Insights の接続文字列
APPINSIGHTS_CONNECTION_STRING = os.environ.get("APPINSIGHTS_CONNECTION_STRING")
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(connection_string=APPINSIGHTS_CONNECTION_STRING))
logger.setLevel(logging.INFO)

# ---------------------------
# Azure Blob Storage 設定
# ---------------------------
#Azure Blob Storage の接続文字列、コンテナ名
AZURE_CONNECTION_STRING = os.environ.get("AZURE_CONNECTION_STRING")
CONTAINER_NAME = "index-test"

blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

# ---------------------------
# 画面タイトル
# ---------------------------
st.title("Azure Blob Storage ファイル管理")

# 🔹 1. ファイルアップロード
st.header("📤 ファイルをアップロード")

uploaded_file = st.file_uploader("アップロードするファイルを選択", type=["pdf", "txt", "jpg", "png", "docx"])

if uploaded_file is not None:
    try:
        blob_client = container_client.get_blob_client(uploaded_file.name)

        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with open(uploaded_file.name, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        st.success(f"✅ {uploaded_file.name} をアップロードしました！")
        logger.info(f"Uploaded file: {uploaded_file.name}")

        os.remove(uploaded_file.name)

    except Exception as e:
        st.error(f"❌ アップロードに失敗しました: {e}")
        logger.error(f"Upload error: {e}")

# 🔹 2. ファイル一覧表示 & 削除
st.header("🗂️ 保存されているファイル一覧")

blobs = container_client.list_blobs()
blob_list = [blob.name for blob in blobs]

if blob_list:
    selected_file = st.selectbox("削除するファイルを選択", blob_list)

    if st.button("🗑️ 選択したファイルを削除"):
        try:
            blob_client = container_client.get_blob_client(selected_file)
            blob_client.delete_blob()
            st.success(f"✅ {selected_file} を削除しました！")
            st.experimental_rerun()

        except Exception as e:
            st.error(f"❌ 削除に失敗しました: {e}")
else:
    st.info("⚠️ 現在、ストレージにファイルはありません。")

# ---------------------------
# 🔽 3. ログ表示（ページ下部）
# ---------------------------
st.markdown("---")
st.header("📄 Application Insights ログ")

if st.button("▶️ ログを表示する"):
    # Application Insights 
    # アプリケーションIDとAPIキーを設定
    app_id = os.environ.get("AI_APP_ID")
    api_key = os.environ.get("AI_API_KEY")

    query = """
    traces
    | where message contains "[PromptFlowPromptLog]"
    | order by timestamp desc
    | project timestamp, message
    | take 100
    """

    url = f"https://api.applicationinsights.io/v1/apps/{app_id}/query"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json={"query": query}, headers=headers)

    if response.status_code == 200:
        data = response.json()

        if "tables" in data and data["tables"]:
            columns = data["tables"][0]["columns"]
            rows = data["tables"][0]["rows"]

            col_names = [col["name"] for col in columns]
            df = pd.DataFrame(rows, columns=col_names)

            with st.expander("🔍 ログ一覧を表示 / 非表示", expanded=True):
                st.dataframe(df)
                for _, row in df.iterrows():
                    st.write(f"🕒 {row['timestamp']} - 📩 {row['message']}")
        else:
            st.warning("データが見つかりませんでした。")
    else:
        st.error(f"APIリクエスト失敗: {response.status_code}")
        st.json(response.json())
else:
    st.caption("⬆️ ログを確認したい場合はボタンを押してください。")
