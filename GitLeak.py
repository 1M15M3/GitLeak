#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print "[!_!]ERROR INFO: You have to install requests module."
    exit()

try:
    from bs4 import BeautifulSoup
except ImportError:
    print "[!_!]ERROR INFO: You have to install BeautifulSoup module."
    exit()

import re
import sys
import time
import imp
import argparse
import os

from urllib import quote

import json

try:
    from Config import *
except ImportError:
    print "[!_!]ERROR INFO: Can't find Config file for searching."
    exit()

try:
    from ColorPrint import *
except ImportError:
    print "[!_!]ERROR INFO: Can't find ColorPrint file for printing."
    exit()

HOST_NAME = "https://github.com/"
RAW_NAME = "https://raw.githubusercontent.com/"
SCAN_DEEP = [10, 30, 50, 70, 100]  # Scanning deep according to page searching count and time out seconds
SEARCH_LEVEL = 1  # Code searching level within 1-5, default is 1
MAX_PAGE_NUM = 100  # Maximum results of code searching
MAX_RLT_PER_PAGE = 10  # Maximum results count of per page


class GitPrey(object):
    """
       _______ __  __               __  
      / ____(_) /_/ /   ___  ____ _/ /__
     / / __/ / __/ /   / _ \/ __ `/ //_/
    / /_/ / / /_/ /___/  __/ /_/ / ,<   
    \____/_/\__/_____/\___/\__,_/_/|_|  
                                    

    Author: md5_salt
    Special thanks to Cooper Pei
    """

    def __init__(self, keyword):
        self.keyword = ' '.join(['"%s"'%i for i in keyword.split(' ')])
        self.search_url = "https://github.com/search?o=desc&p={page}&q={keyword}&ref=searchresults&s=&type=Code&utf8=%E2%9C%93"
        self.headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36"}
        self.cookies = ""

    def search_project(self):
        """
        Search related projects with recently indexed sort according to keyword
        :returns: Related projects list
        """
        unique_project_list = []
        self.__auto_login(USER_NAME, PASSWORD)
        info_print('[@_@] Searching projects hard...')

        # Get unique project list of first page searched results
        total_progress = SCAN_DEEP[SEARCH_LEVEL - 1]
        query_string = self.keyword + " -language:" + " -language:".join(LANG_BLACKLIST)
        for i in xrange(total_progress):
            # Print process of searching project
            progress_point = int((i + 1) * (100 / total_progress))
            sys.stdout.write(str(progress_point) + '%|' + '#' * progress_point + '|\r')
            sys.stdout.flush()
            # Search project in each page
            code_url = self.search_url.format(page=1, keyword=quote(query_string))
            page_html_parse = self.__get_page_html(code_url)
            project_list = self.__page_project_list(page_html_parse)    # Project list of per result page
            page_project_num, project_list = len(project_list), list(set(project_list))
            unique_project_list.extend(project_list)    # Extend unique project list of per page
            if page_project_num < MAX_RLT_PER_PAGE:
                break
            project = " -repo:" + " -repo:".join(project_list)
            query_string += project
        # Deal with last progress bar stdout
        sys.stdout.write('100%|' + '#' * 100 + '|\r')
        sys.stdout.flush()
        return unique_project_list

    @staticmethod
    def __page_project_list(page_html):
        """
        Get project list of one searching result page
        :param page_html: Html page content
        :returns: Project list of per page
        """
        cur_par_html = BeautifulSoup(page_html, "lxml")
        project_info = cur_par_html.select("a.text-bold")
        page_project = [project.text for project in project_info if not project.text.endswith('.github.io')]
        return page_project

    def sensitive_info_query(self, project_string):
        """
        Search sensitive information and sensitive file from projects
        :param project_string: Key words string for querying
        :returns: None
        """
        # Output code line with sensitive key words like username.
        info_sig_list = self.__pattern_db_list(INFO_DB)
        file_sig_list = self.__pattern_db_list(FILE_DB)
        file_pattern = " filename:" + " filename:".join(file_sig_list)
        code_dic = {}
        # Most five AND/OR operators in search function.
        for i in xrange(len(info_sig_list)/MAX_INFONUM+1):
            project_pattern = info_sig_list[i*MAX_INFONUM:i*MAX_INFONUM+MAX_INFONUM]
            repo_code_dic = self.__file_content_inspect(project_string, file_pattern, project_pattern)
            code_dic.update(repo_code_dic)
        return code_dic

    def __file_content_inspect(self, project_string, file_pattern, project_pattern):
        """
        Check sensitive code in particular project
        :param content_query_string: Content string for searching
        :param info_sig_match: information signature match regular
        :returns: None
        """
        if not project_pattern: return {}
        query_string = " OR ".join(project_pattern)
        repo_file_dic = self.__file_name_inspect(query_string + project_string + file_pattern)
        repo_code_dic = {}
        for repo_name in repo_file_dic:
            self.__output_project_info(repo_name)
            repo_code_dic[repo_name] = {}  # Set code line dictionary
            for file_url in repo_file_dic[repo_name]:
                file_url_output = "[-] Compromise File: {file_url}"
                file_print(file_url_output.format(file_url=file_url))
                repo_code_dic[repo_name][file_url] = []  # Set code block of project file
                # Read codes from raw file by replace host to raw host.
                code_file = self.__get_page_html(file_url.replace(HOST_NAME, RAW_NAME).replace('blob/', ''))
                for code_line in code_file.split('\n'):
                    if len(repo_code_dic[repo_name][file_url]) > MAX_COUNT_SINGLE_FILE: break
                    if '=' not in code_line and  ':' not in code_line: continue
                    account_code = re.search('|'.join(project_pattern), code_line, re.I)
                    if account_code:
                        code = code_line.encode('utf-8').strip()
                        if len(code) > MAX_LINELEN: continue
                        code_print(code)
                        repo_code_dic[repo_name][file_url].append(code)
                    else:
                        continue
                if len(repo_code_dic[repo_name][file_url]) > MAX_COUNT_SINGLE_FILE or not repo_code_dic[repo_name][file_url]:
                    del repo_code_dic[repo_name][file_url]

        return repo_code_dic

    def __file_name_inspect(self, file_query_string, print_mode=0):
        """
        Inspect sensitive file in particular project
        :param file_query_string: File string for searching
        :returns: None
        """
        page_num = 1
        repo_file_dic = {}
        while page_num <= SCAN_DEEP[SEARCH_LEVEL - 1]:
            check_url = self.search_url.format(page=page_num, keyword=quote(file_query_string))
            page_html = self.__get_page_html(check_url)
            project_html = BeautifulSoup(page_html, 'lxml')
            repo_list = project_html.select('div .d-inline-block.col-10 > a:nth-of-type(2)')
            if not repo_list:
                break
            # Handle file links for each project
            for repo in repo_list:
                file_url = repo.attrs['href']
                cur_project_name = "/".join(file_url.split("/")[1:3])
                if cur_project_name not in repo_file_dic.keys():
                    if print_mode:
                        self.__output_project_info(cur_project_name)
                        file_print("[-] Compromise File:")
                    repo_file_dic[cur_project_name] = []  # Set compromise project item
                if os.path.splitext(file_url)[1].lower() not in EXT_BLACKLIST:
                    repo_file_dic[cur_project_name].append(HOST_NAME + file_url[1:])  # Set compromise project file item
                    if print_mode:
                        file_print(HOST_NAME + file_url[1:])
            page_num += 1

        return repo_file_dic

    @staticmethod
    def __pattern_db_list(file_path):
        """
        Read file name pattern item from signature file
        :param file_path: Pattern file path
        :returns: Signature item list
        """
        item_list = []
        with open(file_path, 'r') as pattern_file:
            item_line = pattern_file.readline()
            while item_line:
                item_list.append(item_line.strip())
                item_line = pattern_file.readline()
        return item_list

    @staticmethod
    def __output_project_info(project):
        """
        Output user information and project information of particular project
        :returns: None
        """
        user_name, project_name = project.split(r"/")
        user_info = "[+_+] User Nickname: {nickname}"
        project_print(user_info.format(nickname=user_name))
        project_info = "[+_+] Project Name: {name}"
        project_print(project_info.format(name=project_name))
        project_info = "[+_+] Project Link: {link}"
        project_print(project_info.format(link=HOST_NAME + project))

    def __auto_login(self, username, password):
        """
        Get cookie for logining GitHub
        :returns: None
        """
        login_request = requests.Session()
        login_html = login_request.get("https://github.com/login", headers=self.headers)
        post_data = {}
        soup = BeautifulSoup(login_html.text, "lxml")
        input_items = soup.find_all('input')
        for item in input_items:
            post_data[item.get('name')] = item.get('value')
        post_data['login'], post_data['password'] = username, password
        login_request.post("https://github.com/session", data=post_data, headers=self.headers)
        self.cookies = login_request.cookies
        if self.cookies['logged_in'] == 'no':
            error_print('[!_!] ERROR INFO: Login Github failed, please check account in config file.')
            exit()

    def __get_page_html(self, url):
        """
        Get parse html page from requesting url
        :param url: Requesting url
        :returns: Parsed html page
        """
        try:
            page_html = requests.get(url, headers=self.headers, cookies=self.cookies, timeout=SCAN_DEEP[SEARCH_LEVEL - 1])
            if page_html.status_code == 429:
                time.sleep(SCAN_DEEP[SEARCH_LEVEL - 1])
                self.__get_page_html(url)
            return page_html.text
        except requests.ConnectionError, e:
            error_print("[!_!] ERROR INFO: There is '%s' problem in requesting html page." % str(e))
            exit()
        except requests.ReadTimeout:
            return ''

def init():
    """
    Initialize GitPrey with module inspection and input inspection
    :return: None
    """
    try:
        imp.find_module('lxml')
    except ImportError:
        error_print('[!_!]ERROR INFO: You have to install lxml module.')
        exit()

    # Get command parameters for searching level and key words
    parser = argparse.ArgumentParser(description="Searching sensitive file and content in GitHub.")
    parser.add_argument("-l", "--level", type=int, choices=range(1, 6), default=1, metavar="level",
                        help="Set search level within 1~5, default is 1.")
    parser.add_argument("-k", "--keywords", metavar="keywords", required=True,
                        help="Set key words to search projects.")
    args = parser.parse_args()

    SEARCH_LEVEL = args.level if args.level else 1
    key_words = args.keywords if args.keywords else ""

    # Print GitPrey digital logo and version information.
    info_print(GitPrey.__doc__)

    keyword_output = "[^_^] START INFO: The key word for searching is: {keyword}"
    info_print(keyword_output.format(keyword=key_words))

    return key_words


def project_miner(key_words):
    """
    Search projects for content and path inspection later.
    :param key_words: key words for searching
    :return:
    """
    # Search projects according to key words and searching level
    _gitprey = GitPrey(key_words)
    total_project_list = _gitprey.search_project()[:MAX_SEARCH_REPO]

    project_info_output = "\n[*_*] PROJECT INFO: Found {num} public projects related to the key words.\n"
    info_print(project_info_output.format(num=len(total_project_list)))

    if not total_project_list:
        return

    # Scan all projects with pattern content
    info_print("[^_^] START INFO: Begin searching sensitive content.")
    result = {}
    for i in xrange(len(total_project_list)/MAX_REPO_SINGLE_SEARCH+1):
            repo_list = total_project_list[i*MAX_REPO_SINGLE_SEARCH:i*MAX_REPO_SINGLE_SEARCH+MAX_REPO_SINGLE_SEARCH]
            # Join projects to together to search
            repo_string = " repo:" + " repo:".join(repo_list)
            result.update(_gitprey.sensitive_info_query(repo_string))
    jsonify_result(result)
    info_print("[^_^] END INFO: Sensitive content searching is done.\n")

def jsonify_result(result):
    with open('static/report.html', 'r') as f:
        html = f.read()

    data = []
    for repo, urls in result.iteritems():
        if not urls: continue
        children = []
        for url, codel in urls.iteritems():
            code = '\n'.join(codel)
            children.append({"code": code, "label": os.path.basename(url), "fileurl": url, "repo": repo})
        data.append({"children": children, "label": repo})

    html = html.replace('[];//gitleak_data_replace', json.dumps(data))
    with open('report.html', 'w') as f:
        f.write(html)

if __name__ == "__main__":
    # Initialize key words input.
    key_words = init()
    # Search related projects depend on key words.
    project_miner(key_words)
