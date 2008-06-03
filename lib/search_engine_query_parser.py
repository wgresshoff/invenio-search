# -*- coding: utf-8 -*-
## $Id$

## This file is part of CDS Invenio.
## Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007, 2008 CERN.
##
## CDS Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## CDS Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with CDS Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

# pylint: disable-msg=C0301

"""CDS Invenio Search Engine query parsers."""

__lastupdated__ = """$Date$"""

__revision__ = "$Id$"

import re
from invenio.config import CFG_INSPIRE_SITE

class SearchQueryParenthesisedParser:
    """Parse search queries containing parenthesis.

    Current implementation is a simple linear parsing that does not support
    nested parenthesis and priority of operators.

    In case there is a need for nested parenthesis and priority of operators,
    the current implementation can be replaced by one that uses expression
    trees as they are more or less a standard way for parsing expressions.

    The method doing the main work is parse_query()

    Input: parse_query("ellis AND (muon OR kaon)")
    Output: list of [operator1, expression1, operator2, expression2, operator3...,expressionN].
    In case of error: Exception is raised
    """

    # string containing the query that will be parsed
    _query = ""
    # operators before and after the current pattern matched during parsing
    _preceding_operator = ""
    _preceding_operator_position = -1

    _following_operator = ""
    _following_operator_position = -1
    # indexes in the parsed query of beginning and end of currently parsed pattern
    _pattern_beginning = 0
    _pattern_end = 0
    # list of parsed patterns and operators
    _patterns = []
    # flag indicating if processed symbols are inside parenthesis
    _inside_parentheses = False
    # all operator symbols recognized in expression
    _operators = ['+', '|', '-']
    # default operator if operator is missing between patterns
    _DEFAULT_OPERATOR = '+'

    # error messages
    _error_message_mismatched_parentheses = "Mismatched parenthesis."
    _error_message_nested_parentheses_not_supported = "Nested parenthesis are currently not supported."

    def __init__(self):
        """Initialize the state of the parser"""
        self._init_parsing()

    def _init_parsing(self, query=""):
        """Initialize variables before parsing """

        self._compile_regular_expressions()

        # clean the query replacing some of the content e.g. replace 'AND' with '+'
        query = self._clean_query(query)
        self._query = query

        self._patterns = []
        self._pattern_beginning = 0
        self._pattern_end = 0

        self._clear_preceding_operator()
        self._clear_following_operator()

        self._inside_parentheses = False

    def _compile_regular_expressions(self):
        """Compiles some of the regular expressions that are used in the class
        for higher performance."""

        # regular expression that matches the contents in single and double quotes
        # taking in mind if they are escaped.
        self._re_quotes_match = re.compile('[^\\\\](".*?[^\\\\]")|[^\\\\](\'.*?[^\\\\]\')')

    def _clean_query(self, query):
        """Clean the query performing replacement of AND, OR, NOT operators with their
        equivalents +, |, - """

        # result of the replacement
        result = ""
        current_position = 0

        for match in self._re_quotes_match.finditer(query):
            # clean the content after the previous quotes and before current quotes
            cleanable_content = query[current_position : match.start()]
            cleanable_content = self._clean_operators(cleanable_content)

            # get the content in the quotas
            quoted_content = match.group(0)

            # append the processed content to the result
            result = result + cleanable_content + quoted_content

            # move current position at the end of the processed content
            current_position = match.end()

        # clean the content from the last appearance of quotes till the end of the query
        cleanable_content = query[current_position : len(query)]
        cleanable_content = self._clean_operators(cleanable_content)
        result = result + cleanable_content

        return result

    def _clean_operators(self, query = ""):
        """Replaces some of the content of the query with equivalent content
        (e.g. replace 'AND' operator with '+' operator) for easier processing after that."""

        query = self._replace_word_case_insensitive(query, "not", "-")
        query = self._replace_word_case_insensitive(query, "and", "+")
        query = self._replace_word_case_insensitive(query, "or", "|")

        return query

    def _replace_word_case_insensitive(self, str, old_word, new_word):
        """Returns a copy of string str where all occurrences of old_word
        are replaced by new_word"""

        regular_expression = re.compile('\\b'+old_word+'\\b', re.IGNORECASE)

        result = regular_expression.sub(new_word, str)

        return result

    def parse_query(self, query=""):
        """Parses the query and generates as an output a list of values
        containing a sequence of patterns and operators
        [operator1, pattern1, operator2, pattern2, operator3, ..., operatorN, patternN]

        Every pattern is either sequence of search terms and operators
        inside parenthesis or sequence of such terms and operators that are
        outside parenthesis. Operators in the list are these operators that
        are between pattern in parenthesis and pattern that is not in parenthesis"""

        # if the query does not contain parentheses we just return it
        if not self._hasQueryParentheses(query):
            # we add the default operator in front of the query
            return [self._DEFAULT_OPERATOR, query]

        self._init_parsing(query)
        # all operator symbols recognized in expression
        inside_quotes = False
        # used for detecting escape sequences. Contains previously processed character.
        previous_character = ""
        # quotes that are recognized
        quotes_symbols = ['"', "'"]
        # contains the quotes symbol when we are between quotes
        current_quotes_symbol = ""

        # iterate through every character in query and perform appropriate action
        for current_index in range(0, len(self._query)):
            character = self._query[current_index]
            # end of the pattern is the current character, which is not included
            self._pattern_end = current_index

            # include all the characters between quotes in the pattern without special processing
            if inside_quotes and character != current_quotes_symbol:
                continue

            # process the quotes if they are not escaped
            if character in quotes_symbols and previous_character != '\\':
                # if we are not inside this should be a beginning of the quotes
                if not inside_quotes:
                    inside_quotes = True
                    current_quotes_symbol = character
                    self._assign_default_values_for_operators_if_necessary()
                # in case we are inside quotes this is the closing quote
                elif inside_quotes and character == current_quotes_symbol:
                    inside_quotes = False
                    current_quotes_symbol = ""
            elif '(' == character and previous_character != '\\':
                self._handle_open_parenthesis()
            elif ')' == character and previous_character != '\\':
                self._handle_close_parenthesis()
            elif character in self._operators:
                self._handle_operator(current_index)
            else:
                self._handle_non_white_space_characters(current_index)

            # hold the previous character to use it when checking for escape sequences
            previous_character = character

        # as far as patterns are appended when reaching parenthesis we should ensure that we append the last pattern
        self._append_last_pattern()

        # check for mismatched parentheses
        if self._inside_parentheses:
            self._raise_error(self._error_message_mismatched_parentheses)

        return self._patterns

    def _hasQueryParentheses(self, query=""):
        """Check if the query contain parentheses inside."""
        if -1 != query.find("("):
            return True

        if -1 != query.find(")"):
            return True

        return False

    def _handle_open_parenthesis(self):
        """Process opening parenthesis in the query."""

        # check if we are already inside parentheses
        if self._inside_parentheses:
            self._raise_error(self._error_message_nested_parentheses_not_supported)

        # both operators preceding and following the pattern before parenthesis
        # are known and also the pattern itself so append them to the result list.
        self._append_preceding_operator()
        self._append_pattern()
        self._append_following_operator()

        # mark that we are inside parenthesis
        self._inside_parentheses = True

        # clear operators because they are already in the result.
        self._clear_preceding_operator()
        self._clear_following_operator()

    def _handle_close_parenthesis(self):
        """Process closing parenthesis in the query."""

        # check if we are inside parentheses
        if not self._inside_parentheses:
            self._raise_error(self._error_message_mismatched_parentheses)

        # append the pattern between the parentheses
        self._append_pattern()
        # mark that we are not inside parenthesis any more
        self._inside_parentheses = False

    def _handle_operator(self, operator_position):
        """Process operator symbols in the query."""
        if self._inside_parentheses:
            return

        operator = self._query[operator_position]

        # if there is no preceding operator that means that this is the first
        # appearance of an operator after closing parenthesis so we assign
        # the value to the preceding operator
        if self._preceding_operator == "":
            self._preceding_operator = operator
            self._preceding_operator_position = operator_position
            # move the beginning of the patter after the operator
            self._pattern_beginning = operator_position + 1

            # if this is the operator preceding the query, we are not supposed
            # to know the following operator because we are parsing beginning
            self._clear_following_operator()
        # if the preceding operator is assigned then this operator is currently
        # the following operator of the pattern. If there operator after it will replace it
        else:
            self._following_operator = operator
            self._following_operator_position = operator_position

    def _handle_non_white_space_characters(self, character_postition):
        """Process all non white characters that are not operators, quotes
        or parenthesis and are not inside parenthesis or quotes"""

        character = self._query[character_postition]

        # if the character is white space or we are in parentheses we skip processing
        if character.isspace() or self._inside_parentheses:
            return

        self._assign_default_values_for_operators_if_necessary()

    def _assign_default_values_for_operators_if_necessary(self):
        """Assign default values for preceding or following operators if this is necessary."""

        # if the preceding operator is empty that means we are starting to parse a new
        # pattern but there is no operator in front of it. In this case assign default
        # value to preceding operator
        if self._preceding_operator == "":
            self._preceding_operator = self._DEFAULT_OPERATOR
            self._preceding_operator_position = -1
        # otherwise we are now parsing a pattern and can assign current value for following operator
        else:
            # default operator is assigned as a value and will be changed next
            # time operator character is reached
            self._following_operator = self._DEFAULT_OPERATOR
            self._following_operator_position = -1

    def _append_pattern(self):
        """Appends the currently parsed pattern to the list with results"""
        begin = self._calculate_pattern_beginning()
        end = self._calculate_pattern_end()

        current_pattern = self._query[begin : end]
        current_pattern = current_pattern.strip()

        #don't append empty patterns
        if current_pattern != "":
            self._patterns.append(current_pattern)

        # move the beginning of next pattern at the end of current pattern
        self._pattern_beginning = self._pattern_end+1

    def _append_preceding_operator(self):
        """Appends the operator preceding current pattern to the list with results."""
        if self._preceding_operator != "":
            self._patterns.append(self._preceding_operator)
        else:
            self._patterns.append(self._DEFAULT_OPERATOR)

    def _append_following_operator(self):
        """Appends the operator following current pattern to the list with results."""
        if self._following_operator != "":
            self._patterns.append(self._following_operator)

    def _append_last_pattern(self):
        """Appends the last pattern from the query to the list with results.
        Operator preceding this pattern is also appended."""
        self._pattern_end = self._pattern_end+1
        self._append_preceding_operator()
        self._append_pattern()

        # if the last pattern was empty but default preceding operator
        # is appended, then clean it
        if self._patterns[-1] == self._DEFAULT_OPERATOR:
            self._patterns = self._patterns[0 : -1] # remove last element

    def _calculate_pattern_beginning(self):
        """Calculates exact beginning of a pattern taking in mind positions of
        operator proceeding the pattern."""
        # if there is an operator character before the pattern it should not be
        # included in the pattern
        if self._pattern_beginning < self._preceding_operator_position:
            return self._preceding_operator_position + 1

        return self._pattern_beginning

    def _calculate_pattern_end(self):
        """Calculates exact end of a pattern taking in mind positions of
        operator following the pattern."""
        # if there is an operator character after the pattern it should not be
        # included in the pattern
        if self._pattern_end > self._following_operator_position and self._following_operator_position != -1:
            return self._following_operator_position

        return self._pattern_end

    def _clear_preceding_operator(self):
        """Cleans the value of the preceding operator"""
        self._preceding_operator = ""
        # after the value is cleaned the position is also cleaned. We accept -1 for cleaned value.
        self._preceding_operator_position = -1

    def _clear_following_operator(self):
        """Cleans the value of the following operator"""
        self._following_operator = ""
        # after the value is cleaned the position is also cleaned. We accept -1 for cleaned value.
        self._following_operator_position = -1

    def _raise_error(self, error_message_text):
        """Raises an exception with the specified error message"""
        raise InvenioWebSearchQueryParserException(error_message_text)

class InvenioWebSearchQueryParserException(Exception):
    """Exception for parsing errors."""
    def __init__(self, message):
        """Initialization."""
        self.message = message

class SpiresToInvenioSyntaxConverter:
    """Converts queries defined with SPIRES search syntax into queries
    that use Invenio search syntax.
    """

    # Dictionary containing the matches between SPIRES keywords
    # and their corresponding Invenio keywords or fields
    # SPIRES keyword : Invenio keyword or field
    _SPIRES_TO_INVENIO_KEYWORDS_MATCHINGS = {
        # affiliation
            ' affiliation ' : ' 700__u:',
            ' affil ' : ' 700__u:',
            ' aff ' : ' 700__u:',
            ' af ' : ' 700__u:',
            ' institution ' : ' 700__u:',
            ' inst ' : ' 700__u:',
        # any field
            ' any ' : ' anyfield:',
        # bulletin
            ' bb ' : ' 037__a:',
            ' bbn ' : ' 037__a:',
            ' bull ' : ' 037__a:',
            ' bulletin-bd ' : ' 037__a:',
            ' bulletin-bd-no ' : ' 037__a:',
            ' eprint ' : ' 037__a:',
        # citation / reference
            ' c ' : ' reference:',
            ' citation ' : ' reference:',
            ' cited ' : ' reference:',
            ' jour-vol-page ' : ' reference:',
            ' jvp ' : ' reference:',
        # collaboration
            ' collaboration ' : ' 710__g:',
            ' collab-name ' : ' 710__g:',
            ' cn ' : ' 710__g:',
        # conference number
            ' conf-number ' : ' 111__g:',
            ' cnum ' : ' 111__g:',
        # country
            ' cc ' : ' 044__a:',
            ' country ' : ' 044__a:',
        # date
            ' date ' : ' 269__c:',
            ' d ' : ' 269__c:',
        # date added
            ' date-added ' : ' 961__x:',
            ' dadd ' : ' 961__x:',
            ' da ' : ' 961__x:',
        # date updated
            ' date-updated ' : ' 961__c:',
            ' dupd ' : ' 961__c:',
            ' du ' : ' 961__c:',
        # first author
            ' fa ' : ' 100__a:',
            ' first-author ' : ' 100__a:',
        # author
            ' a ':' author:',
            ' au ':' author:',
            ' author ':' author:',
            ' name ':' author:',
        # exact author
        # this is not a real keyword match. It is pseudo keyword that
        # will be replaced later with author search
            ' ea ':' exactauthor:',
            ' exact-author ':' exactauthor:',
        # experiment
            ' exp ' : ' experiment:',
            ' experiment ' : ' experiment:',
            ' expno ' : ' experiment:',
            ' sd ' : ' experiment:',
            ' se ' : ' experiment:',
        # journal
            ' journal ' : ' journal:',
            ' j ' : ' journal:',
            ' published_in ' : ' journal:',
            ' spicite ' : ' journal:',
            ' vol ' : ' journal:',
        # journal page
            ' journal-page ' : ' 773__c:',
            ' jp ' : ' 773__c:',
        # journal year
            ' journal-year ' : ' 773__y:',
            ' jy ' : ' 773__y:',
        # key
            ' key ' : ' 970__a:',
            ' irn ' : ' 970__a:',
            ' record ' : ' 970__a:',
            ' document ' : ' 970__a:',
            ' documents ' : ' 970__a:',
        # keywords
            ' k ' : ' keyword:',
            ' keywords ' : ' keyword:',
        # note
            ' note ' : ' 500__a:',
            ' n ' : ' 500__a:',
        # old title
            ' old-title ' : ' 246__a:',
            ' old-t ' : ' 246__a:',
            ' ex-ti ' : ' 246__a:',
            ' et ' : ' 246__a:',
        # ppf subject
            ' ppf-subject ' : ' 650__a:',
            ' ps ' : ' 650__a:',
            ' scl ' : ' 650__a:',
            ' status ' : ' 650__a:',
        # report number
            ' r ' : ' reportnumber:',
            ' rn ' : ' reportnumber:',
            ' rept ' : ' reportnumber:',
            ' report ' : ' reportnumber:',
            ' report-num ' : ' reportnumber:',
        # title
            ' t ' : ' title:',
            ' ti ' : ' title:',
            ' title ' : ' title:',
            ' with-language ' : ' title:',
        # topic
            ' topic ' : ' 653__a:',
            ' tp ' : ' 653__a:',
            ' hep-topic ' : ' 653__a:',
            ' desy-keyword ' : ' 653__a:',
            ' dk ' : ' 653__a:',
        # replace all the keywords without match with empty string
        # this will remove the noise from the unknown keywrds in the search
        # and will in all fields for the words following the keywords

        # category
            ' arx ' : ' ',
            ' category ' : ' ',
        # coden
            ' bc ' : ' ',
            ' browse-only-indx ' : ' ',
            ' coden ' : ' ',
            ' journal-coden ' : ' ',
        # energy
            ' e ' : ' ',
            ' energy ' : ' ',
            ' energyrange-code ' : ' ',
        # exact author
            ' ea ' : ' ',
            ' exact-author ' : ' ',
        # exact expression number
            ' ee ' : ' ',
            ' exact-exp ' : ' ',
            ' exact-expno ' : ' ',
        # field code
            ' f ' : ' ',
            ' fc ' : ' ',
            ' field ' : ' ',
            ' field-code ' : ' ',
        # hidden note
            ' hidden-note ' : ' ',
            ' hn ' : ' ',
        # ppf
            ' ppf ' : ' ',
            ' ppflist ' : ' ',
        # primarch
            ' parx ' : ' ',
            ' primarch ' : ' ',
        # slac topics
            ' ppfa ' : ' ',
            ' slac-topics ' : ' ',
            ' special-topics ' : ' ',
            ' stp ' : ' ',
        # test index
            ' test ' : ' ',
            ' testindex ' : ' ',
        # texkey
            ' texkey ' : ' ',
        # type code
            ' tc ' : ' ',
            ' ty ' : ' ',
            ' type ' : ' ',
            ' type-code ' : ' '
        }

    def __init__(self):
        """Initialize the state of the converter"""
        self._compile_regular_expressions()

    def _compile_regular_expressions(self):
        """Compiles some of the regular expressions that are used in the class
        for higher performance."""

        # regular expression that matches the contents in single and double quotes
        # taking in mind if they are escaped.
        self._re_quotes_match = re.compile('[^\\\\](".*?[^\\\\]")|[^\\\\](\'.*?[^\\\\]\')')

        # regular expression that matches author patterns
        # the groups defined in this regular expression are used in the method
        # _convert_spires_author_search_to_invenio_author_search(...) In case
        # of changing them, correct also the code in this method
        self._re_author_match = re.compile(
            # author:ellis, jacqueline
            r'\bauthor:\s*(?P<surname1>\w+),\s*(?P<name1>\w{3,})\b(?= and | or | not |$)' + '|' + \
            # author:jacqueline ellis
            r'\bauthor:\s*(?P<name2>\w+)\s+(?!and |or |not )(?P<surname2>\w+)\b(?= and | or | not |$)' + '|' +\
            # author:ellis, j.
            r'\bauthor:\s*(?P<surname3>\w+),\s*(?P<name3>\w{1,2})\b\.?(?= and | or | not |$)' + '|' +\
            # author: ellis, j. r.
            r'\bauthor:\s*(?P<surname4>\w+),\s*(?P<name4>\w+)\b\.?\s+(?!and |or |not )(?P<middle_name4>\w+)\b\.?' + '|' +\
            # author j. r. ellis
            r'\bauthor:\s*(?P<name5>\w+)\b\.?\s+(?!and |or |not )(?P<middle_name5>\w+)\b\.?\s+(?!and |or |not )(?P<surname5>\w+)\b\.?',
            re.IGNORECASE)

        # regular expression that matches exact author patterns
        # the group defined in this regular expression is used in method
        # _convert_spires_exact_author_search_to_invenio_author_search(...)
        # in case of changes correct also the code in this method
        self._re_exact_author_match = re.compile(r'\bexactauthor:(?P<author_name>.*?\b)(?= and | or | not |$)', re.IGNORECASE)

        # regular expression that matches search term, its conent (words that
        # are searched)and the operator preceding the term. In case that the
        # names of the groups defined in the expression are changed, the
        # chagned should be reflected in the code that use it.
        self._re_search_term_pattern_match = re.compile(r'\b(?P<combine_operator>find|and|or|not)\s+(?P<search_term>title:|keyword:)(?P<search_content>.*?\b)(?= and | or | not |$)', re.IGNORECASE)

        # regular expression used to split string by white space as separator
        self._re_split_pattern = re.compile(r'\s*')

        # regular expression matching date after pattern
        self._re_date_after_match = re.compile(r'\b(d|date)\b\s*(after|>)\s*(?P<year>\d{4})\b', re.IGNORECASE)

        # regular expression matching date after pattern
        self._re_date_before_match = re.compile(r'\b(d|date)\b\s*(before|<)\s*(?P<year>\d{4})\b', re.IGNORECASE)

    def convert_query(self, query):
        """Converts the query from SPIRES syntax to Invenio syntax

        Queries are assumed SPIRES queries only if they start with FIND or F"""

        # assume that only queries starting with FIND are SPIRES queries
        if query.lower().startswith("find "):
            # these calls are before keywords replacement becuase when keywords
            # are replaced, date keyword is replaced by specific field search
            # and the DATE keyword is not match in DATE BEFORE or DATE AFTER
            query = self._convert_spires_date_before_to_invenio_span_query(query)
            query = self._convert_spires_date_after_to_invenio_span_query(query)

            # call to _replace_spires_keywords_with_invenio_keywords should be at the
            # beginning because the next methods use the result of the replacement
            query = self._replace_spires_keywords_with_invenio_keywords(query)

            query = self._convert_spires_author_search_to_invenio_author_search(query)
            query = self._convert_spires_exact_author_search_to_invenio_author_search(query)
            query = self._convert_spires_truncation_to_invenio_truncation(query)
            query = self._expand_search_patterns(query)

            # remove FIND in the beginning of the query as it is not necessary in Invenio
            query = query[5:]

        return query


    def _convert_spires_date_after_to_invenio_span_query(self, query):
        """Converts date after SPIRES search term into invenio span query"""


        def create_replacement_pattern(match):
            """method used for replacement with regular expression"""
            return 'year:' + match.group('year') + '->9999'

        query = self._re_date_after_match.sub(create_replacement_pattern, query)

        return query


    def _convert_spires_date_before_to_invenio_span_query(self, query):
        """Converts date before SPIRES search term into invenio span query"""

        # method used for replacement with regular expression
        def create_replacement_pattern(match):
            return 'year:' + '0->' + match.group('year')

        query = self._re_date_before_match.sub(create_replacement_pattern, query)

        return query


    def _expand_search_patterns(self, query):
        """Expands search queries.

        If a search term is followed by several words e.g.
        author: ellis or title:THESE THREE WORDS it is exoanded to
        author: ellis or title:THESE or title:THREE or title:WORDS.

        For a combining operator is used the operator befor the search term

        Not all the search terms are expanded this way, but only a short
        list of them"""

        def create_replacement_pattern(match):
            result = ''
            search_term = match.group('search_term')
            combine_operator = match.group('combine_operator')
            search_content = match.group('search_content').strip()

            for word in self._re_split_pattern.split(search_content):
                if combine_operator.lower() == 'find':
                    result = 'find ' + search_term + word
                    combine_operator = 'and'
                else:
                    result =  result + ' ' + combine_operator + ' ' + search_term + word
            return result.strip()

        query = self._re_search_term_pattern_match.sub(create_replacement_pattern, query)
        return query

    def _convert_spires_truncation_to_invenio_truncation(self, query):
        """Replace SPIRES truncation symbol # with invenio trancation symbol *"""
        return query.replace('#', '*')

    def _convert_spires_exact_author_search_to_invenio_author_search(self, query):
        """Converts SPIRES search patterns for exact author into search pattern
        for invenio"""

        # method used for replacement with regular expression
        def create_replacement_pattern(match):
            # the regular expression where this group name is defined is in
            # the method _compile_regular_expressions()
            return 'author:"' + match.group('author_name') + '"'

        query = self._re_exact_author_match.sub(create_replacement_pattern, query)

        return query

    def _convert_spires_author_search_to_invenio_author_search(self, query):
        """Converts SPIRES search patterns for authors to search patterns in invenio
        that give similar results to the spires search."""

        # result of the replacement
        result = ""
        current_position = 0

        for match in self._re_author_match.finditer(query):

            result = result + query[current_position : match.start()]

            # the regular expression where these group names are defined is in
            # the method _compile_regular_expressions()
            result = result + \
                self._create_author_search_pattern(match.group('name1'), None, match.group('surname1')) + \
                self._create_author_search_pattern(match.group('name2'), None, match.group('surname2')) + \
                self._create_author_search_pattern(match.group('name3'), None, match.group('surname3')) + \
                self._create_author_search_pattern(match.group('name4'), match.group('middle_name4'), match.group('surname4')) + \
                self._create_author_search_pattern(match.group('name5'), match.group('middle_name5'), match.group('surname5'))

            # move current position at the end of the processed content
            current_position = match.end()

        # append the content from the last match till the end
        result = result + query[current_position : len(query)]

        return result

    def _create_author_search_pattern(self, author_name, author_middle_name, author_surname):
        """Creates search patter for author by given author's name and surname.

        When the pattern is executed in invenio search, it produces results
        similar to the results of SPIRES search engine."""

        AUTHOR_KEYWORD = 'author:'

        # we expect to have at least surname
        if author_surname == '' or author_surname == None:
            return ''

        # SPIRES use dots at the end of the abbreviations of the names
        # CERN don't use dots at the end of the abbreviations of the names
        # when we are running Invenio with SPIRES date we add the dots, otherwise we don't
        dot_symbol = ' '
        if CFG_INSPIRE_SITE:
            dot_symbol = "."

        # if there is middle name we expect to have also name and surname
        # ellis, j. r. ---> ellis, j* r*
        # j r ellis ---> ellis, j* r*
        # ellis, john r. ---> ellis, j* r* or ellis, j. r. or ellis, jo. r.
        if author_middle_name != None and author_middle_name != '':
            search_pattern = AUTHOR_KEYWORD +  '"' + author_surname + ', ' + author_name + '*' + ' ' + author_middle_name + '*"'
            if len(author_name)>1:
                search_pattern = search_pattern + ' or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name[0] + dot_symbol  + author_middle_name + dot_symbol  + '" or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name[0:2] + dot_symbol + author_middle_name + dot_symbol + '"'
            return search_pattern

        # ellis ---> "ellis"
        if author_name == '' or author_name == None:
            return AUTHOR_KEYWORD + author_surname

        # ellis, j ---> "ellis, j*"
        if len(author_name) == 1:
            return AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name + '*"'

        # ellis, jacqueline ---> "ellis, jacqueline" or "ellis, j.*" or "ellis, j" or "ellis, ja.*" or "ellis, ja" or "ellis, jacqueline *"
        # in case we don't use SPIRES data, the ending dot is ommited.

        if len(author_name) > 1:
            return AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name + '" or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name[0] + dot_symbol + '*" or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name[0] + '" or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name[0:2] + dot_symbol + '*" or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name[0:2] + '" or ' +\
                AUTHOR_KEYWORD + '"' + author_surname + ', ' + author_name + ' *"'


    def _replace_spires_keywords_with_invenio_keywords(self, query):
        """Replaces SPIRES keywords that have directly
        corresponding Invenio keywords

        Replacements are done only in content that is not in quotes."""

        # result of the replacement
        result = ""
        current_position = 0

        for match in self._re_quotes_match.finditer(query):
            # clean the content after the previous quotes and before current quotes
            cleanable_content = query[current_position : match.start()]
            cleanable_content = self._replace_all_spires_keywords_in_string(cleanable_content)

            # get the content in the quotas
            quoted_content = match.group(0)

            # append the processed content to the result
            result = result + cleanable_content + quoted_content

            # move current position at the end of the processed content
            current_position = match.end()

        # clean the content from the last appearance of quotes till the end of the query
        cleanable_content = query[current_position : len(query)]
        cleanable_content = self._replace_all_spires_keywords_in_string(cleanable_content)
        result = result + cleanable_content

        return result

    def _replace_all_spires_keywords_in_string(self, query):
        """Replaces all SPIRES keywords in the string with their
        corresponding Invenio keywords"""

        for spires_keyword, invenio_keyword in self._SPIRES_TO_INVENIO_KEYWORDS_MATCHINGS.iteritems():
            query = self._replace_keyword(query, spires_keyword, invenio_keyword)

        return query

    def _replace_keyword(self, query, old_keyword, new_keyword):
        """Replaces old keyword in the query with a new keyword"""

        # perform case insensitive replacement with regular expression
        regex_string = r'\b((?<=find)|(?<=and)|(?<=or)|(?<=not))\s*' + old_keyword + r'\b'
        regular_expression = re.compile(regex_string, re.IGNORECASE)
        result = regular_expression.sub(new_keyword, query)

        return result