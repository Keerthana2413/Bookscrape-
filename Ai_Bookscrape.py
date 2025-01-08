import streamlit as st
import mysql.connector
import pandas as pd
from mysql.connector import Error
from sqlalchemy import create_engine
import requests
import json

# Fetch books from Google Books API
def fetch_books(query, api_key, max_books=100):
    books = []  # To store all books
    start_index = 0
    max_results = 40  # API limit for maxResults per request

    while len(books) < max_books:
        # Make the API request
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": query,
                "startIndex": start_index,
                "maxResults": max_results,
                "key": api_key,
            },
        )

        # Check for errors
        if response.status_code != 200:
            st.error(f"Error: {response.status_code}, {response.text}")
            break

        data = response.json()
        items = data.get("items", [])
        if not items:  # If no more items are returned, stop fetching
            break

        books.extend(items)  # Add the books to the list
        start_index += max_results  # Update the start index for the next request

    return books[:max_books]  # Return only up to the max_books limit


# Extract book data into a structured format
def extract_book_data(books, query):
    extracted_books = []
    for book in books:
        volume_info = book.get("volumeInfo", {})
        sale_info = book.get("saleInfo", {})
        list_price = sale_info.get("listPrice", {})
        retail_price = sale_info.get("retailPrice", {})

        extracted_books.append(
            {
                "book_id": book.get("id"),
                "search_key": query,  # Example hardcoded key
                "book_title": volume_info.get("title"),
                "book_authors": ", ".join(volume_info.get("authors", [])),
                "book_description": volume_info.get("description"),
                "publisher": volume_info.get("publisher"),
                "pageCount": volume_info.get("pageCount"),
                "language": volume_info.get("language"),
                "averageRating": volume_info.get("averageRating"),
                "ratingsCount": volume_info.get("ratingsCount"),
                "amount_listPrice": list_price.get("amount"),
                "currency_listPrice": list_price.get("currencyCode"),
                "amount_retailPrice": retail_price.get("amount"),
                "currency_retailPrice": retail_price.get("currencyCode"),
                "buyLink": sale_info.get("buyLink"),
                "publishedDate": volume_info.get("publishedDate"),
            }
        )

    return extracted_books  # Convert to DataFrame


# Database connection string
host = 'localhost'
username = 'root'
password = 'root'
port = 3306
database = 'BookScrape'
connection_string = f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}"
engine = create_engine(connection_string)


# Connect to MySQL Database
def connect_to_database():
    try:
        connection = mysql.connector.connect(
            host="Localhost",
            user="root",
            password="root",
            database="API"
        )
        if connection.is_connected():
            return connection
    except Error as e:
        st.Error(f"Error:{e}")


# Define SQL queries
questions = {
    "Check Availability of eBooks vs Physical Books":"""select isEbook,count(isEbook) As total_books from ai_bookscrape group by isEbook;""",
    "Find the Publisher with the Most Books Published":"""select publisher,count(publisher) As MostBooksPublished from ai_bookscrape where publisher is NOT NULL AND publisher !='No publisher' group by publisher order by MostBooksPublished Desc LIMIT 1;""",
    "Identify the Publisher with the Highest Average Rating":"""select publisher,avg(averageRating) As Highest_Avgrating from ai_bookscrape where publisher is NOT NULL AND publisher !='No publisher'and averageRating !='No averageRatingscount' group by publisher order by Highest_Avgrating DESC LIMIT 1;""",
    "Get the Top 5 Most Expensive Books by Retail Price":"""select book_title,Max(amount_retailPrice) as Most_Expensive_Books from ai_bookscrape where amount_retailPrice != 'No retail price' group by book_title order by Most_Expensive_Books DESC LIMIT 5;""",
    "Find Books Published After 2010 with at Least 500 Pages":"""select book_title,year,pageCount from ai_bookscrape where year>2010 and pageCount >=500 ;""",
    "Find the Average Page Count for eBooks vs Physical Books":"""select isEbook,avg(pageCount) as Avg_page_count from ai_bookscrape where pageCount != 'No page count' and pageCount is NOT NULL group by isEbook;""",
    "Find the Top 3 Authors with the Most Books":"""select book_authors,book_title,count(book_authors) as Top_3_Authors from ai_bookscrape where TRIM(book_authors) != 'NA' group by book_authors,book_title order by Top_3_Authors DESC LIMIT 3;""",
    "List Publishers with More than 10 Books":"""select publisher,count(publisher) as publisher_count from ai_bookscrape where publisher is NOT NULL AND publisher !='No publisher'group by publisher order by publisher_count DESC LIMIT 10;""",
    "Find the Average Page Count for Each Category":"""select categories,avg(pageCount) as Avg_pageCount from ai_bookscrape where pageCount != 'No page count' and pageCount is NOT NULL and TRIM(categories) !='NA' group by categories order by Avg_pageCount ASC;""",
    "Retrieve Books with More than 3 Authors":"""select book_title,book_authors from ai_bookscrape where length(book_authors) - length(replace(book_authors,',',''))+1>3 and TRIM(book_authors) != 'NA';""",
    "Books with Ratings Count Greater Than the Average":"""select book_title,ratingsCount from ai_bookscrape where ratingsCount > (select avg(ratingsCount) from ai_bookscrape) and ratingsCount is not null and ratingscount !='No ratings count';""",
    "Books with the Same Author Published in the Same Year":"""select book_authors,year as publisheryear,group_concat(book_title) as book_tiles from ai_bookscrape WHERE TRIM(book_authors) != 'NA' AND year !='No Year' GROUP BY book_authors, year HAVING COUNT(book_authors) > 1 ORDER BY book_authors, year;""",
    "Books with a Specific Keyword in the Title":"""select book_title from ai_bookscrape where book_title like '%AI%' order by book_title;""",
    "Year with the Highest Average Book Price":"""select year as publisheryear,avg(amount_listPrice) as Highest_Avg_price from ai_bookscrape where year !='No Year' and amount_listPrice !='No list price' group by publisheryear order by Highest_Avg_price DESC;""",
    "Count Authors Who Published 3 Consecutive Years":"""SELECT a.year AS publisheryear, COUNT(DISTINCT a.year) AS authors_with_consecutive_years 
    FROM ai_bookscrape a
    JOIN ai_bookscrape b ON a.book_authors = b.book_authors
    JOIN ai_bookscrape c ON a.book_authors = c.book_authors
    WHERE a.year = b.year - 1
    AND b.year = c.year - 1
    AND a.year != 'No Year'
    AND b.year != 'No Year'
    AND c.year != 'No Year'
    GROUP BY a.year
    LIMIT 0, 1000;""",
    "Write a SQL query to find authors who have published books in the same year but under different publishers. Return the authors, year, and the COUNT of books they published in that year.":"""select book_authors,year as publisheryear,count(Distinct publisher)as publisher_count,count(book_title) as bookcount from ai_bookscrape where year !='No Year' and TRIM(book_authors) != 'NA' group by book_authors,publisheryear having count(DISTINCT publisher)>1;""",
    "Create a query to find the average amount_retailPrice of eBooks and physical books. Return a single result set with columns for avg_ebook_price and avg_physical_price. Ensure to handle cases where either category may have no entries.":"""select COALESCE(avg(case when isEbook=1 then amount_retailprice end),0) as avg_ebook_price,COALESCE(avg(case when isEbook=2 then amount_retailprice end),0) as avg_physical_price  from ai_bookscrape;""",
    "Write a SQL query to identify books that have an averageRating that is more than two standard deviations away from the average rating of all books. Return the title, averageRating, and ratingsCount for these outliers.":"""WITH stats AS (SELECT AVG(averageRating) AS avg_rating,STDDEV(averageRating) AS stddev_rating FROM ai_bookscrape),outliers AS (SELECT book_title,averageRating,ratingsCount
    FROM ai_bookscrape, stats WHERE averageRating > avg_rating + 2 * stddev_rating OR averageRating < avg_rating - 2 * stddev_rating)SELECT book_title,averageRating,ratingsCount FROM outliers;""",
    "Create a SQL query that determines which publisher has the highest average rating among its books, but only for publishers that have published more than 10 books. Return the publisher, average_rating, and the number of books published.":"""
    SELECT publisher,AVG(averageRating) AS avg_rating,COUNT(book_title) AS num_books FROM ai_bookscrape GROUP BY publisher HAVING COUNT(book_title) > 10 ORDER BY avg_rating DESC;"""
}

# Streamlit interface with two tabs
st.title("Bookscrape Explorer")
tab_selection = st.radio("Select Tab", ["Book Extraction", "SQL Query Execution"])

if tab_selection == "Book Extraction":
    st.subheader("Book Extraction from API")
    query = st.text_input('Enter the book name:')
    
    if st.button('Fetch Books'):
        books = fetch_books(query, api_key='AIzaSyAl0N2PHjeo9c7qo9Cn5COhLfIuo8HbLCk', max_books=100)
        extracted_books = extract_book_data(books, query)
        df = pd.DataFrame(extracted_books)
        st.session_state['df'] = df  # Save DataFrame to session state
        st.dataframe(df)  

    if st.button('Save to Database'):
        if 'df' in st.session_state:
            df = st.session_state['df']  # Retrieve DataFrame from session state
            df.to_sql(
                name="sample",
                con=engine,
                index=False,
                if_exists="replace",
                chunksize=10000,
            )
            st.success("Books data saved successfully to the database.")
        else:
            st.error("No data available to save. Please fetch books first.")

elif tab_selection == "SQL Query Execution":
    st.subheader("Execute SQL Queries")
    selected_question = st.selectbox("Select a question to execute:", list(questions.keys()))
    st.write(f"**Selected Question:** {selected_question}")
    query = questions.get(selected_question, "")
    
    if st.button("Run Query"):
        connection = connect_to_database()
        if connection:
            try:
                # Execute the query and fetch results into a DataFrame
                df = pd.read_sql(query, connection)
                st.write("**Query Output:**")
                st.dataframe(df)  # Display the result as a dataframe
            except Error as e:
                st.error(f"Error executing query: {e}")
            finally:
                connection.close()
        else:
            st.error("Failed to connect to the database.")
else:
    st.error("Please select a valid tab.")
