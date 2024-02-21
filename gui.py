import tkinter as tk
from tkinter import ttk, scrolledtext
import time
from trag_server.rag_search import search
from trag_server.sql_database import get_connection
from trag_server.openai import ask_gpt
from textwrap import dedent, indent
import requests
import json
import os
import re

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

waiting_on_chat_response = False
waiting_on_search_results = False

terminal_font = ("Courier New", 10)  # Change the size as needed
background_color = "black"
foreground_color = "green"
input_background_color = "#1c1c1c"

# Initialize a variable for the selected document
selected_document = None

def get_app():
    conn = get_connection()

    def query_for_document_list():
        # This function should be connected to your actual database query
        c = conn.cursor()
        c.execute("select name, status from Document")
        rows = c.fetchall()
        doc_list = sorted([(d[0], d[1]) for d in rows], key=lambda d: 0 if d[1] == "done" else 1 if d[1] == "in progress" else 2)
        c.close()
        return doc_list

    def chatbot_response(user_message):
        response_limit = 100
        rag_search_results = search(["main"], user_message, 6)
        rag_search_results_chunk = '\n'.join(rag_search_results)
        prompt = dedent(f"""
        <|user|>
        ### PDF Search Results
{indent(rag_search_results_chunk, '        ')}
        ### End of Results


        {user_message}

        <|assistant|>
        """).strip()

        print(prompt)

        response = ask_gpt(prompt)

        return response

    def append_chat_message(chat_widget, message, user="User"):
        if not message.strip():
            return

        chat_widget.config(state=tk.NORMAL)
        if user == "User":
            chat_widget.insert(tk.END, user + ": " + message + "\n")
        else:
            chat_widget.insert(tk.END, message + "\n", 'chatbot')  # Tag this message as 'chatbot'
        chat_widget.config(state=tk.DISABLED)
        chat_widget.yview(tk.END)

        message_entry.delete(0, tk.END)

        if user == "User":
            response = chatbot_response(message)
            append_chat_message(chat_widget, response, user="Chatbot")

    def refresh_document_list(tree: ttk.Treeview):
        selection = tree.selection()
        selected_item = None
        if selection:
            selected_item = tree.item(selection[0], 'values')

        for i in tree.get_children():
            tree.delete(i)

        for title, status in query_for_document_list():
            icon = "✓" if status == "done" else "🛠" if status == "in progress" else "⏳"
            color = "green" if status == "done" else "orange" if status == "in progress" else "gray"
            item = tree.insert("", "end", values=(icon, title, status), tags=(color,))
            tree.tag_configure(color, foreground=color)

            if selected_item and title == selected_item[1]:
                tree.selection_set(item)

        tree.after(1000, lambda: refresh_document_list(tree))

    root = tk.Tk()
    root.title("T-Rag: Your Tiny Document Assistant")
    root.resizable(False, False)  # Make the window non-resizable

    # Split the main window into two frames
    left_frame = tk.Frame(root, width=400)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    right_frame = tk.Frame(root)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # Create a notebook for Chat and Quick Search tabs
    notebook = ttk.Notebook(left_frame)
    chat_tab = tk.Frame(notebook)  # Frame for Chat tab
    search_tab = tk.Frame(notebook)  # Frame for Quick Search tab
    notebook.add(search_tab, text="Quick Search")
    notebook.add(chat_tab, text="Ask T-Rag")
    notebook.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    def append_search_result(search_widget, message, is_search_query=False):
        search_entry.delete(0, tk.END)

        search_widget.config(state=tk.NORMAL)
        # Simulate left (search query) and right (result) alignment with indentation
        if is_search_query:
            formatted_message = "\n🔍 " + message + "\n"
            search_widget.insert(tk.END, formatted_message, 'query')
        else:
            formatted_message = "   " + message + " ✔️\n"
            search_widget.insert(tk.END, formatted_message, 'result')
        search_widget.config(state=tk.DISABLED)
        search_widget.yview(tk.END)

    def perform_search(event=None):
        query = search_entry.get()

        if not query.strip():
            return

        search_entry.delete(0, tk.END)

        append_search_result(search_results_area, query, is_search_query=True)
        results = search(["main"], query, 6)
        print(results)
        result_message = "\n ---".join([f"\nResult {i+1} of {len(results)}\n{r}" for i, r in enumerate(results)])
        append_search_result(search_results_area, result_message)

    # Chat interface on the Chat tab
    chat_area = scrolledtext.ScrolledText(chat_tab, state=tk.DISABLED, bg='white')
    chat_area.pack(padx=10, pady=(5,0), fill=tk.BOTH, expand=True)
    chat_area.tag_configure('chatbot', foreground='blue')

    message_label = tk.Label(chat_tab, text="Ask:")
    message_label.pack(padx=10, pady=(5, 0), side=tk.LEFT)

    message_entry = tk.Entry(chat_tab)
    message_entry.pack(padx=10, fill=tk.X, side=tk.LEFT, expand=True)
    message_entry.bind("<Return>", lambda event: append_chat_message(chat_area, message_entry.get(), user="User"))

    send_button = tk.Button(chat_tab, text="Send", command=lambda: append_chat_message(chat_area, message_entry.get()))
    send_button.pack(padx=(0,10), pady=(5, 10), side=tk.LEFT)
    send_button.config(command=lambda: append_chat_message(chat_area, message_entry.get(), user="User"))

    # Quick Search interface on the Quick Search tab
    search_results_area = scrolledtext.ScrolledText(search_tab, state=tk.DISABLED, bg='white')
    search_results_area.pack(padx=10, pady=(5, 0), fill=tk.BOTH, expand=True)

    search_results_area.tag_configure('query', foreground='blue')
    search_results_area.tag_configure('result', foreground='green')

    search_label = tk.Label(search_tab, text="Search:")
    search_label.pack(padx=10, pady=(5, 0), side=tk.LEFT)

    search_entry = tk.Entry(search_tab)
    search_entry.pack(padx=10, fill=tk.X, side=tk.LEFT, expand=True)
    search_entry.bind("<Return>", perform_search)

    search_button = tk.Button(search_tab, text="Search")
    search_button.pack(padx=(0,10), pady=(5, 10), side=tk.LEFT)

    search_button.config(command=perform_search)

    # Document table on the right
    style = ttk.Style()
    style.configure("Treeview", rowheight=25)
    style.configure("Treeview.Column", font=('Helvetica', 10))
    style.configure("Treeview", font=('Helvetica', 10))

    # Define a treeview widget with an additional column
    doc_tree = ttk.Treeview(right_frame, columns=('Status', 'Document', 'StatusText'), show='headings')
    doc_tree.heading('#1', text="")
    doc_tree.heading('#2', text='Document')
    doc_tree.heading('#3', text="")

    # Set the column width and alignment if necessary
    doc_tree.column('#1', anchor='center', width=30)
    doc_tree.column('#2', anchor='w', width=200)
    doc_tree.column('#3', anchor='center', width=75)

    # Pack the treeview
    doc_tree.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    # Initial population of the treeview
    refresh_document_list(doc_tree)

    # # Load an image
    # image = ttk.Image.open("TRag.jpg")
    # photo = ttk.ImageTk.PhotoImage(image)

    # # Create a label with the image and place it in the bottom right corner
    # label = tk.Label(root, image=photo)
    # label.image = photo  # Keep a reference to the image to prevent it from being garbage collected
    # label.place(relx=1, rely=1, anchor=tk.SE)

    return root

if __name__ == "__main__":
    get_app().mainloop()
