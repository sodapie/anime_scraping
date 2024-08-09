
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from janome.tokenizer import Tokenizer
from wordcloud import WordCloud
import requests
from bs4 import BeautifulSoup

# 日本語フォントを表示するための設定値
fpath = '/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc'

def get_full_review(review_url):
    """Fetch the full review from the given review URL."""
    review_response = requests.get(review_url)
    review_soup = BeautifulSoup(review_response.content, 'html.parser')
    full_review_element = review_soup.find(class_='p-mark__review')
    return full_review_element.text.strip() if full_review_element else None

def scrape_reviews(page_url):
    """Scrape reviews from the given page URL."""
    response = requests.get(page_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all elements with class 'p-mark'
    p_mark_elements = soup.find_all(class_='p-mark')
    
    # Initialize lists to store scores and reviews
    scores = []
    reviews = []
    
    # Loop through each 'p-mark' element
    for p_mark in p_mark_elements:
        # Find the score within the 'p-mark' element
        score_element = p_mark.find(class_='c-rating__score')
        if score_element:
            score_text = score_element.text.strip()
            if score_text != '-':
                try:
                    score = float(score_text)
                    scores.append(score)
                except ValueError:
                    continue
            else:
                continue
        
        # Find the review within the 'p-mark' element
        review_element = p_mark.find(class_='p-mark__review')
        if review_element:
            # Check if there is a "続きを読む" link
            read_more_link = review_element.find('a')
            if read_more_link and 'href' in read_more_link.attrs:
                # Get the full review from the link
                full_review_url = "https://filmarks.com" + read_more_link['href']
                full_review = get_full_review(full_review_url)
                reviews.append(full_review)
            else:
                reviews.append(review_element.text.strip())
        else:
            reviews.append(None)
    
    # Create a DataFrame from the lists of scores and reviews
    df = pd.DataFrame({
        'score': scores,
        'review': reviews
    })
    
    return df, soup

def scrape_all_reviews(base_url):
    # Initialize a list to store all DataFrames
    all_dfs = []

    # Start with the first page
    page_url = base_url
    while page_url:
        df, soup = scrape_reviews(page_url)
        all_dfs.append(df)
        
        # Find the next page link
        next_page_element = soup.find('a', class_='c2-pagination__next')
        if next_page_element and 'href' in next_page_element.attrs:
            next_page_url = next_page_element['href']
            page_url = "https://filmarks.com" + next_page_url
        else:
            page_url = None

    # Concatenate all DataFrames into one
    final_df = pd.concat(all_dfs, ignore_index=True)
    return final_df

# Input
base_url = st.text_input('ベースとなるURLを入力してください', placeholder='（例）https://filmarks.com/animes/4206/5682')
if 'data' not in st.session_state:
    st.session_state.data = None

if st.button('スクレイピングを実行'):
    with st.spinner('スクレイピング中...'):
        df = scrape_all_reviews(base_url)
        st.session_state.data = df
        st.success('スクレイピング完了')

if st.session_state.data is not None:
    df = st.session_state.data
    
    score_range = st.selectbox('スコア範囲を選択', 
                               ['0-1', '1-2', '2-3', '3-4', '4-5'])

    # 品詞を選択（複数選択）
    word_class = st.multiselect('品詞を選択',['名詞','形容詞','動詞','副詞'])

    # 指定した単語をストップワードとして除外
    stop_text = st.text_input("カンマ区切りでストップワードを設定")
    stop_list = [x.strip() for x in stop_text.split(",")]

    # 単語群をカンマ区切りで入力
    target_words_text = st.text_input("カンマ区切りでターゲットとなる単語群を入力")
    target_words = [x.strip() for x in target_words_text.split(",")]

    if st.button('データ処理'):
        # スコア範囲でフィルタリング
        score_min, score_max = map(float, score_range.split('-'))
        filtered_df = df[(df['score'] >= score_min) & (df['score'] < score_max)]
        
        # Noneを空文字列に置き換え
        filtered_df = filtered_df.copy()
        filtered_df.loc[:, 'review'] = filtered_df['review'].apply(lambda x: x if x is not None else '')
        
        # レビューのテキストを連結
        input_text = ' '.join(filtered_df['review'])

        
        word_list = [] #分割後の形態素を一次格納する空のリストを用意
        
        for token in Tokenizer().tokenize(input_text):
            split_token = token.part_of_speech.split(',')
            if split_token[0] in word_class:
                word_list.append(token.base_form)
        

        if target_words:
            # 各ターゲット単語の出現回数をカウント
            word_counts = {word: word_list.count(word) for word in target_words}

            # データフレームに変換
            df_counts = pd.DataFrame(list(word_counts.items()), columns=['単語', '回数'])

            # 横棒グラフを作成
            st.bar_chart(df_counts.set_index('単語'))

        if word_list:
            # 単語の頻度集計
            df_freq = pd.DataFrame(word_list, columns=['単語'])
            df_freq['回数'] = 1  
            df_freq_sorted = df_freq.groupby('単語').sum().reset_index().sort_values('回数', ascending=False)

            # インデックスをリセット
            df_freq_sorted.reset_index(inplace=True, drop=True)
            # 単語の先頭にインデックス番号を挿入
            df_freq_sorted['単語（ソート用）'] = df_freq_sorted.index.astype(str).str.zfill(2) + '_' + df_freq_sorted['単語']
            
            ### word cloud作成 ###

            # word cloud側の仕様で、単語リストの要素を空白区切りに連結する
            word_space = ' '.join(map(str, word_list)) #数字が入っていた場合の対策として、strに変換してから連結

            # word cloudの設定(フォントの設定)
            wc = WordCloud(background_color='white', colormap='summer', font_path=fpath, width=800, height=400, stopwords=stop_list)
                                                              # オプション stopwords=[単語リスト]で除外対象単語（ストップワード）を設定可能
                                                              # 設定例：stopwords=['テレビ', '商品']
            wc.generate(word_space)
            
            ##出力画像の大きさの指定
            plt.figure(figsize=(10, 5))

            ## 目盛り削除など見た目の修正
            plt.tick_params(labelbottom=False,
                            labelleft=False,
                            labelright=False,
                            labeltop=False,
                            length=0)

            st.image(wc.to_array())
        else:
            st.write('指定された品詞に一致する単語がありませんでした。')

