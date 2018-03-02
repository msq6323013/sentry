from __future__ import absolute_import

from collections import namedtuple
from parsimonious.grammar import Grammar, NodeVisitor

__all__ = ('parse_rules', 'dump_schema', 'load_schema')

VERSION = 1

# Grammar is defined in EBNF syntax.
ownership_grammar = Grammar(r"""

ownership = line+

line = _ (comment / rule / empty) newline?

rule = _ matcher owners

matcher      = _ matcher_tag identifier
matcher_tag  = (matcher_type sep)?
matcher_type = "url" / "path"

owners       = _ owner+
owner        = _ team_prefix identifier
team_prefix  = "#"?

comment = ~r"#[^\r\n]*"

# TODO: make more specific
identifier = ~r"\S+"

sep     = ":"
space   = " "
empty   = ""
newline = ~r"[\r\n]"
_       = space*

""")


class Rule(namedtuple('Rule', 'matcher owners')):
    """
    A Rule represents a single line in an Ownership file.
    This line contains a Matcher and a list of Owners.
    """

    def dump(self):
        return {
            'matcher': self.matcher.dump(),
            'owners': [o.dump() for o in self.owners],
        }

    @classmethod
    def load(cls, data):
        return cls(
            Matcher.load(data['matcher']),
            [Owner.load(o) for o in data['owners']],
        )


class Matcher(namedtuple('Matcher', 'type pattern')):
    """
    A Matcher represents a type:pattern pairing for use in
    comparing with an Event.

    type is either `path` or `url` at this point.

    TODO(mattrobenolt): pattern needs to be parsed into a regex

    Examples:
        url:example.com
        path:src/*
        src/*
    """

    def dump(self):
        return {
            'type': self.type,
            'pattern': self.pattern,
        }

    @classmethod
    def load(cls, data):
        return cls(
            data['type'],
            data['pattern'],
        )


class Owner(namedtuple('Owner', 'type identifier')):
    """
    An Owner represents a User or Team who owns this Rule.

    type is either `user` or `team`.

    Examples:
        foo@example.com
        #team
    """

    def dump(self):
        return {
            'type': self.type,
            'identifier': self.identifier,
        }

    @classmethod
    def load(cls, data):
        return cls(
            data['type'],
            data['identifier'],
        )


class OwnershipVisitor(NodeVisitor):
    visit_comment = visit_empty = lambda *a: None

    def visit_ownership(self, node, children):
        return filter(None, children)

    def visit_line(self, node, children):
        _, line, _ = children
        comment_or_rule_or_empty = line[0]
        if comment_or_rule_or_empty:
            return comment_or_rule_or_empty

    def visit_rule(self, node, children):
        _, matcher, owners = children
        return Rule(matcher, owners)

    def visit_matcher(self, node, children):
        _, tag, identifier = children
        return Matcher(tag, identifier)

    def visit_matcher_tag(self, node, children):
        if not children:
            return 'path'
        tag, = children
        type, _ = tag
        return type[0].text

    def visit_owners(self, node, children):
        _, owners = children
        return owners

    def visit_owner(self, node, children):
        _, is_team, pattern = children
        return Owner('team' if is_team else 'user', pattern)

    def visit_team_prefix(self, node, children):
        return bool(children)

    def visit_identifier(self, node, children):
        return node.text

    def generic_visit(self, node, children):
        return children or node


def parse_rules(data):
    """Convert a raw text input into a Rule tree"""
    tree = ownership_grammar.parse(data)
    return OwnershipVisitor().visit(tree)


def dump_schema(rules):
    """Convert a Rule tree into a JSON schema"""
    return {
        '$version': VERSION,
        'rules': [r.dump() for r in rules],
    }


def load_schema(schema):
    """Convert a JSON schema into a Rule tree"""
    if schema['$version'] != VERSION:
        raise RuntimeError('Invalid schema $version: %r' % schema['$version'])
    return [Rule.load(r) for r in schema['rules']]