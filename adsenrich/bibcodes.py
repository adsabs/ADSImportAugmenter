import os
import re
import roman
import string

from adsputils import load_config

from adsenrich.data import *
from adsenrich.utils import issn2info, name2bib, u2asc

proj_home = os.getenv("PWD", None)
conf = load_config(proj_home=proj_home)

REGEX_PAGE_ROMAN_NUMERAL = re.compile(r'^[IVXLCDMivxlcdm\.\+\s,-]+$')


class BibstemException(Exception):
    pass


class NoPubYearException(Exception):
    pass


class NoBibcodeException(Exception):
    pass


class BibcodeGenerator(object):
    def __init__(self, bibstem=None, volume=None, token=None, url=None):
        if not token:
            token = conf.get("_API_TOKEN", None)
        if not url:
            url = conf.get("_API_URL", None)

        self.api_token = token
        self.api_url = url
        self.bibstem = bibstem
        self.volume = volume

    def _int_to_letter(self, integer):
        try:
            return string.ascii_letters[int(integer) - 1]
        except Exception as err:
            return integer

    def _get_author_init(self, record):
        author_init = "."
        special_char = {'&ETH;': 'ETH',
                        '&eth;': 'eth',
                        '&THORN;': 'TH',
                        '&thorn;': 'th'}
        author_list = record.get("authors", [])
        if author_list:
            first_author = record.get("authors", [])[0]
            if first_author:
                author_name = first_author.get("name", None)
                if author_name:
                    namestring = None
                    if author_name.get("collab", None):
                        namestring = author_name.get("collab")
                    elif author_name.get("surname", None):
                        namestring = author_name.get("surname")
                    if namestring:
                        try:
                            namestring = u2asc(namestring.strip())
                            for k, v in special_char.items():
                                namestring = namestring.replace(k, v)
                            author_init = namestring[0].upper()
                        except:
                            pass
        return author_init

    def _get_pubyear(self, record):
        try:
            pub_year = record.get("publication", {}).get("pubYear", None)
        except Exception as err:
            raise NoPubYearException(err)
        else:
            return pub_year

    def _get_volume(self, record):
        if self.volume:
            return self.volume
        else:
            try:
                volume = record.get("publication", {}).get("volumeNum", None)
                if "-" in volume:
                    vol_list = volume.strip().split("-")
                    volume = vol_list[0]
            except Exception as err:
                volume = "."
            return volume

    def _get_issue(self, record):
        try:
            issue = str(record.get("publication", {}).get("issueNum", None))
        except Exception as err:
            issue = None
        return issue

    def _get_pagenum(self, record):
        pagination = record.get("pagination", None)
        if pagination:
            fpage = pagination.get("firstPage", None)
            epage = pagination.get("electronicID", None)
            rpage = pagination.get("pageRange", None)
            if fpage:
                page = fpage
            elif epage:
                page = epage
            elif rpage:
                page = rpage
            else:
                page = "."
            page = page.replace(",", "")
            if REGEX_PAGE_ROMAN_NUMERAL.search(page):
                page = roman.fromRoman(page.upper())
            return page
        else:
            return "."

    def _deletter_page(self, page):
        is_letter = None
        if "L" in page or "l" in page:
            page = page.replace("L", ".").replace("l", ".")
            is_letter = "L"
        elif "P" in page or "p" in page:
            page = page.replace("P", "").replace("p", "")
            is_letter = "P"
        elif "S" in page or "s" in page:
            page = page.replace("S", "").replace("s", "")
            is_letter = "S"
        elif "A" in page:
            page = page.replace("A", "")
            is_letter = "A"
        elif "C" in page:
            page = page.replace("C", "")
            is_letter = "C"
        elif "E" in page:
            page = page.replace("E", "")
            is_letter = "E"
        elif "T" in page or "t" in page:
            page = page.replace("T", "").replace("t", ".")
            is_letter = "T"
        return (page, is_letter)

    def _get_normal_pagenum(self, record):
        page = self._get_pagenum(record)
        is_letter = None
        if page:
            (page, is_letter) = self._deletter_page(page)
            if len(str(page)) >= 5:
                page = str(page)[-5:]
            else:
                page = page.rjust(4, ".")
            if is_letter:
                page = page[-4:]
        return (page, is_letter)

    def _get_converted_pagenum(self, record):
        try:
            page = self._get_pagenum(record)
            (page, is_letter) = self._deletter_page(page)
            if page:
                page_a = None
                if len(str(page)) >= 6:
                    page = page[-6:]
                    page_a = self._int_to_letter(page[0:2])
                    page = page[2:]
                if page_a:
                    if not is_letter:
                        is_letter = page_a
        except Exception as err:
            page = None
            is_letter = None
        return page, is_letter

    def _get_bibstem(self, record):
        if self.bibstem:
            return self.bibstem
        else:
            bibstem = None
            if not bibstem:
                issn_publisher = record.get("publication", {}).get("publisher", None)
                if issn_publisher == "Zenodo":
                    bibstem = "zndo."
            if not bibstem:
                issn_rec = []
                issn_rec = record.get("publication", {}).get("ISSN", [])
                for i in issn_rec:
                    issn = i.get("issnString", None)
                    if issn:
                        issn = str(issn)
                        if len(issn) == 8:
                            issn = issn[0:4] + "-" + issn[4:]
                        bibstem = ISSN_DICT.get(issn, None)
                        if bibstem:
                            return bibstem
                        if not bibstem:
                            bibstem = issn2info(
                                token=self.api_token,
                                url=self.api_url,
                                issn=issn,
                                return_info="bibstem",
                            )
                        if bibstem:
                            return bibstem
                if not bibstem:
                    journal_name = record.get("publication", {}).get("pubName", None)
                    if journal_name:
                        bibstem = name2bib(
                            token=self.api_token,
                            url=self.api_url,
                            name=journal_name,
                        )
        if bibstem:
            return bibstem
        else:
            raise BibstemException("Bibstem not found.")

    def make_bibcode(self, record, bibstem=None, volume=None):
        try:
            year = self._get_pubyear(record)
        except Exception as err:
            year = None
        try:
            if not bibstem:
                bibstem = self._get_bibstem(record)
        except Exception as err:
            bibstem = None
        try:
            if not volume:
                volume = self._get_volume(record)
        except Exception as err:
            volume = ""
        try:
            author_init = self._get_author_init(record)
        except Exception as err:
            author_init = "."
        if not (year and bibstem):
            raise NoBibcodeException(
                "You're missing year and or bibstem -- no bibcode can be made!"
            )
        else:
            bibstem = bibstem.ljust(5, ".")
            volume = volume.rjust(4, ".")
            author_init = author_init.rjust(1, ".")
            issue = None

            # Special bibstem, page, volume, issue handling
            if bibstem in IOP_BIBSTEMS:
                # IOP get converted_pagenum/letters for six+ digit pages
                (pageid, is_letter) = self._get_converted_pagenum(record)
                if bibstem == "JCAP.":
                    # JCAP is an IOP journal
                    try:
                        issue = self._get_issue(record)
                        volume = issue.rjust(4, ".")
                        issue = None
                    except:
                        issue = None
                elif bibstem == "ApJL.":
                    # ApJ/L are IOP journals
                    bibstem = "ApJ.."
                    issue = "L"
                elif bibstem == "JaJAP":
                    # JaJAP/JJAPS are IOP journals
                    issue = self._get_issue(record)
                    if "S" in issue:
                        bibstem = "JJAPS"
                if is_letter:
                    if not issue:
                        issue = is_letter
                if issue and (len(pageid) > 4):
                    pageid = pageid[-4:]
                

            elif bibstem in APS_BIBSTEMS:
                # APS get converted_pagenum/letters for six+ digit pages
                (pageid, is_letter) = self._get_converted_pagenum(record)
                if is_letter:
                    if not issue:
                        issue = is_letter

            elif bibstem in OUP_BIBSTEMS:
                # APS get converted_pagenum/letters for six+ digit pages
                (pageid, is_letter) = self._get_converted_pagenum(record)
                if is_letter:
                    if not issue:
                        issue = is_letter

            elif bibstem in AIP_BIBSTEMS:
                # AIP: AIP Conf gets special handling
                (pageid, is_letter) = self._get_converted_pagenum(record)
                if bibstem == "AIPC.":
                    if is_letter:
                        if not issue:
                            issue = is_letter
                else:
                    issue = self._int_to_letter(self._get_issue(record))

            elif bibstem in SPRINGER_BIBSTEMS:
                # Springer get converted_pagenum/letters for six+ digit pages
                (pageid, is_letter) = self._get_normal_pagenum(record)
                if bibstem == "JHEP." or bibstem == "JCAP.":
                    try:
                        issue = self._get_issue(record)
                        volume = issue.rjust(4, ".")
                        issue = None
                    except:
                        issue = None
                if is_letter:
                    if not issue:
                        issue = is_letter

            elif bibstem in WILEY_BIBSTEMS:
                strip_list = ["GB", "PA", "RG", "RS", "TC"]
                page = self._get_pagenum(record)
                newpage = page
                is_letter = ""
                for substr in strip_list:
                    newpage = re.sub(substr, ".", newpage)
                newpage = re.sub(r"^[ABCDEFGLMQSW]0?", ".", newpage)

                if newpage[0] == "L":
                    newpage = newpage[1:]
                    is_letter = "L"
                while re.search(r"^0", newpage):
                    newpage = re.sub(r"^0", "", newpage)
                if is_letter:
                    plength = 4
                else:
                    plength = 5
                if len(newpage) > plength:
                    newpage = newpage[-plength:]
                elif len(newpage) < plength:
                    newpage = newpage.rjust(plength, ".")
                pageid = is_letter + newpage

            elif bibstem in ["zndo."]:
                try:
                    zenodo_pid = record.get("persistentIDs", {})
                    zenodo_doi = None
                    for d in zenodo_pid:
                        if d.get("DOI", None):
                            zenodo_doi = d.get("DOI")
                    if zenodo_doi:
                        zenodo_id = zenodo_doi.split("/")[-1].replace("zenodo.", "")
                        pageid = zenodo_id[-4:].rjust(4, ".")
                        zenodo_id = zenodo_id[0:-4]
                        if zenodo_id:
                            issue = zenodo_id[-1]
                            zenodo_id = zenodo_id[0:-1]
                        else:
                            issue = "."
                        volume = zenodo_id.rjust(4, ".")
                except:
                    pass

            else:
                (pageid, is_letter) = self._get_normal_pagenum(record)
                if is_letter:
                    if not issue:
                        issue = is_letter

            # for stem.conf, stem.work, stem.data, stem.book etc...
            if len(bibstem) == 9:
                volume = ""

            if not issue:
                pageid = pageid.rjust(5, ".")
                issue = ""
            else:
                pageid = pageid.rjust(4, ".")

            try:
                bibcode = year + bibstem + volume + issue + pageid + author_init
                if len(bibcode) != 19:
                    raise Exception("Malformed bibcode, wrong length!")
            except Exception as err:
                bibcode = None
            return bibcode
