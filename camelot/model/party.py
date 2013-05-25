#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================

"""Set of classes to store persons, organizations, relationships and
contact mechanisms

These structures are modeled like described in 'The Data Model Resource Book'
by Len Silverston, Chapter 2
"""

import datetime

from sqlalchemy.ext import hybrid
from sqlalchemy.types import Date, Unicode, Integer, Boolean
from sqlalchemy.sql.expression import and_

from sqlalchemy import orm, schema, sql, ForeignKey

from camelot.admin.entity_admin import EntityAdmin
from camelot.core.document import documented_entity
from camelot.core.orm import ( Entity, using_options, Field, ManyToMany,  
                               ManyToOne, OneToMany, ColumnProperty )
from camelot.core.utils import ugettext_lazy as _
from camelot.model.type_and_status import Status
import camelot.types
from camelot.view.controls import delegates
from camelot.view.forms import Form, TabForm, HBoxForm, WidgetOnlyForm

from authentication import end_of_times

class GeographicBoundary( Entity ):
    """The base class for Country and City"""
    using_options( tablename = 'geographic_boundary' )
    code = Field( Unicode( 10 ) )
    name = Field( Unicode( 40 ), required = True )
    
    row_type = schema.Column( Unicode(40), nullable = False )
    __mapper_args__ = { 'polymorphic_on' : row_type }

    @ColumnProperty
    def full_name( self ):
        return self.code + ' ' + self.name

    def __unicode__( self ):
        return u'%s %s' % ( self.code, self.name )

class Country( GeographicBoundary ):
    """A subclass of GeographicBoundary used to store the name and the
    ISO code of a country"""
    using_options( tablename = 'geographic_boundary_country' )
    geographicboundary_id = Field( Integer, 
                                   ForeignKey('geographic_boundary.id'), 
                                   primary_key = True )

    __mapper_args__ = {'polymorphic_identity': 'country'}

    @classmethod
    def get_or_create( cls, code, name ):
        country = Country.query.filter_by( code = code ).first()
        if not country:
            country = Country( code = code, name = name )
            orm.object_session( country ).flush()
        return country

    class Admin( EntityAdmin ):
        form_size = ( 700, 150 )
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        list_display = ['name', 'code']

Country = documented_entity()(Country)

class City( GeographicBoundary ):
    """A subclass of GeographicBoundary used to store the name, the postal code
    and the Country of a city"""
    using_options( tablename = 'geographic_boundary_city' )
    country = ManyToOne( Country, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    geographicboundary_id = Field( Integer, 
                                   ForeignKey('geographic_boundary.id'), 
                                   primary_key = True )

    __mapper_args__ = {'polymorphic_identity': 'city'}
    
    @classmethod
    def get_or_create( cls, country, code, name ):
        city = City.query.filter_by( code = code, country = country ).first()
        if not city:
            city = City( code = code, name = name, country = country )
            orm.object_session( city ).flush()
        return city

    class Admin( EntityAdmin ):
        verbose_name = _('City')
        verbose_name_plural = _('Cities')
        form_size = ( 700, 150 )
        list_display = ['code', 'name', 'country']

City = documented_entity()(City)

class Address( Entity ):
    """The Address to be given to a Party (a Person or an Organization)"""
    using_options( tablename = 'address' )
    street1 = Field( Unicode( 128 ), required = True )
    street2 = Field( Unicode( 128 ) )
    city = ManyToOne( City, 
                      required = True, 
                      ondelete = 'cascade', 
                      onupdate = 'cascade',
                      lazy = 'subquery' )
    party_addresses = OneToMany( 'PartyAddress' )
                         
    def name( self ):
        return sql.select( [self.street1 + ', ' + GeographicBoundary.full_name],
                           whereclause = (GeographicBoundary.id == self.city_geographicboundary_id))
    
    name = ColumnProperty( name, deferred = True )

    @classmethod
    def get_or_create( cls, street1, street2, city ):
        address = cls.query.filter_by( street1 = street1, street2 = street2, city = city ).first()
        if not address:
            address = cls( street1 = street1, street2 = street2, city = city )
            orm.object_session( address ).flush()
        return address

    def __unicode__( self ):
        return u'%s, %s' % ( self.street1 or '', self.city or '' )

    class Admin( EntityAdmin ):
        verbose_name = _('Address')
        verbose_name_plural = _('Addresses')
        list_display = ['street1', 'street2', 'city']
        form_size = ( 700, 150 )
        field_attributes = {'street1':{'minimal_column_width':30}}
        
        def get_depending_objects( self, address ):
            for party_address in address.party_addresses:
                yield party_address
                if party_address.party != None:
                    yield party_address.party
            
Address = documented_entity()( Address )

class PartyContactMechanismAdmin( EntityAdmin ):
    form_size = ( 700, 200 )
    verbose_name = _('Contact mechanism')
    verbose_name_plural = _('Contact mechanisms')
    list_search = ['party_name', 'mechanism']
    list_display = ['party_name', 'mechanism', 'comment', 'from_date', ]
    form_display = Form( ['mechanism', 'comment', 'from_date', 'thru_date', ] )
    field_attributes = {'party_name':{'minimal_column_width':25, 'editable':False},
                        'mechanism':{'minimal_column_width':25,
                                     'editable':True,
                                     'nullable':False,
                                     'name':_('Mechanism'),
                                     'delegate':delegates.VirtualAddressDelegate}}

    def get_depending_objects(self, contact_mechanism ):
        party = contact_mechanism.party
        if party and (party not in Party.query.session.new):
            yield party
            
    def get_compounding_objects( self, contact_mechanism ):
        if contact_mechanism.contact_mechanism:
            yield contact_mechanism.contact_mechanism

class PartyPartyContactMechanismAdmin( PartyContactMechanismAdmin ):
    list_search = ['party_name', 'mechanism']
    list_display = ['mechanism', 'comment', 'from_date', ]

class Party( Entity ):
    """Base class for persons and organizations.  Use this base class to refer to either persons or
    organisations in building authentication systems, contact management or CRM"""
    using_options( tablename = 'party' )

    addresses = OneToMany( 'PartyAddress', lazy = True, cascade="all, delete, delete-orphan" )
    contact_mechanisms = OneToMany( 'PartyContactMechanism', 
                                    lazy = 'select', 
                                    cascade='all, delete, delete-orphan' )
    shares = OneToMany( 'SharedShareholder', inverse = 'established_to', cascade='all, delete, delete-orphan' )
    directed_organizations = OneToMany( 'DirectedDirector', inverse = 'established_to', cascade='all, delete, delete-orphan' )
    status = Status()
    categories = ManyToMany( 'PartyCategory', 
                             tablename='party_category_party', 
                             remote_colname='party_category_id',
                             local_colname='party_id')
    
    row_type = schema.Column( Unicode(40), nullable = False )
    __mapper_args__ = { 'polymorphic_on' : row_type }

    @property
    def name( self ):
        return ''

    def _get_contact_mechanism( self, described_by ):
        """Get a specific type of contact mechanism
        """
        for party_contact_mechanism in self.contact_mechanisms:
            contact_mechanism = party_contact_mechanism.contact_mechanism
            if contact_mechanism != None:
                mechanism = contact_mechanism.mechanism
                if mechanism != None:
                    if mechanism[0] == described_by:
                        return mechanism
                    
    def _set_contact_mechanism( self, described_by, value ):
        """Set a specific type of contact mechanism
        """
        assert value[0] in camelot.types.VirtualAddress.virtual_address_types
        for party_contact_mechanism in self.contact_mechanisms:
            contact_mechanism = party_contact_mechanism.contact_mechanism
            if contact_mechanism != None:
                mechanism = contact_mechanism.mechanism
                if mechanism != None:
                    if mechanism[0] == described_by:
                        if value and value[1]:
                            contact_mechanism.mechanism = value
                        else:
                            session = orm.object_session( party_contact_mechanism )
                            self.contact_mechanisms.remove( party_contact_mechanism )
                            if party_contact_mechanism.id:
                                session.delete( party_contact_mechanism )
                        return
        if value and value[1]:
            contact_mechanism = ContactMechanism( mechanism = value )
            party_contact_mechanism = PartyContactMechanism( contact_mechanism = contact_mechanism )
            self.contact_mechanisms.append( party_contact_mechanism )
            
    @hybrid.hybrid_property
    def email( self ):
        return self._get_contact_mechanism( u'email' )
    
    @email.setter
    def email_setter( self, value ):
        return self._set_contact_mechanism( u'email', value )
    
    @email.expression
    def email_expression( self ):
        return orm.aliased( ContactMechanism ).mechanism

    @hybrid.hybrid_property
    def phone( self ):
        return self._get_contact_mechanism( u'phone' )
    
    @phone.setter
    def phone_setter( self, value ):
        return self._set_contact_mechanism( u'phone', value )    
    
    @phone.expression
    def phone_expression( self ):
        return orm.aliased( ContactMechanism ).mechanism

    @hybrid.hybrid_property
    def fax( self ):
        return self._get_contact_mechanism( u'fax' )
    
    @fax.setter
    def fax_setter( self, value ):
        return self._set_contact_mechanism( u'fax', value )    
    
    @fax.expression
    def fax_expression( self ):
        return orm.aliased( ContactMechanism ).mechanism 

    def _get_address_field( self, name ):
        for party_address in self.addresses:
            return getattr( party_address, name )
        
    def _set_address_field( self, name, value ):
        if not self.addresses:
            address = PartyAddress()
            self.addresses.append( address )
        address = self.addresses[0]
        setattr( address, name, value )
        if address.street1==None and address.street2==None and address.city==None:
            session = orm.object_session( address )
            if address in session.new:
                session.expunge( address )
                self.addresses.remove( address )
            else:
                session.delete( address )
        
    @hybrid.hybrid_property
    def street1( self ):
        return self._get_address_field( u'street1' )
    
    @street1.setter
    def street1_setter( self, value ):
        return self._set_address_field( u'street1', value )

    @hybrid.hybrid_property
    def street2( self ):
        return self._get_address_field( u'street2' ) 
    
    @street2.setter
    def street2_setter( self, value ):
        return self._set_address_field( u'street2', value )    
    
    @hybrid.hybrid_property
    def city( self ):
        return self._get_address_field( u'city' )
    
    @city.setter
    def city_setter( self, value ):
        return self._set_address_field( u'city', value )
    
    def full_name( self ):

        aliased_organisation = sql.alias( Organization.table )
        aliased_person = sql.alias( Person.table )
        
        return sql.functions.coalesce( sql.select( [sql.functions.coalesce(aliased_person.c.first_name,'') + ' ' + sql.functions.coalesce(aliased_person.c.last_name, '')],
                                                   whereclause = and_( aliased_person.c.party_id == self.id ),
                                                   ).limit( 1 ).as_scalar(),
                                       sql.select( [aliased_organisation.c.name],
                                                   whereclause = and_( aliased_organisation.c.party_id == self.id ), 
                                                   ).limit( 1 ).as_scalar() )
    
    full_name = ColumnProperty( full_name, deferred=True )

class Organization( Party ):
    """An organization represents any internal or external organization.  Organizations can include
    businesses and groups of individuals"""
    using_options( tablename = 'organization' )
    party_id = Field( Integer, 
                      ForeignKey('party.id'), 
                      primary_key = True )
    __mapper_args__ = {'polymorphic_identity': u'organization'}
    name = Field( Unicode( 50 ), required = True, index = True )
    logo = Field( camelot.types.Image( upload_to = 'organization-logo' ), deferred = True )
    tax_id = Field( Unicode( 20 ) )
    directors = OneToMany( 'DirectedDirector', inverse = 'established_from', cascade='all, delete, delete-orphan' )
    employees = OneToMany( 'EmployerEmployee', inverse = 'established_from', cascade='all, delete, delete-orphan' )
    suppliers = OneToMany( 'SupplierCustomer', inverse = 'established_to', cascade='all, delete, delete-orphan' )
    customers = OneToMany( 'SupplierCustomer', inverse = 'established_from', cascade='all, delete, delete-orphan' )
    shareholders = OneToMany( 'SharedShareholder', inverse = 'established_from', cascade='all, delete, delete-orphan' )

    def __unicode__( self ):
        return self.name or ''

    @property
    def number_of_shares_issued( self ):
        return sum( ( shareholder.shares for shareholder in self.shareholders ), 0 )

Organization = documented_entity()( Organization )

# begin short person definition
class Person( Party ):
    """Person represents natural persons
    """
    using_options( tablename = 'person' )
    party_id = Field( Integer, 
                      ForeignKey('party.id'), 
                      primary_key = True )
    __mapper_args__ = {'polymorphic_identity': u'person'}
    first_name = Field( Unicode( 40 ), required = True )
    last_name = Field( Unicode( 40 ), required = True )
# end short person definition
    middle_name = Field( Unicode( 40 ) )
    personal_title = Field( Unicode( 10 ) )
    suffix = Field( Unicode( 3 ) )
    sex = Field( Unicode( 1 ), default = u'M' )
    birthdate = Field( Date() )
    martial_status = Field( Unicode( 1 ) )
    social_security_number = Field( Unicode( 12 ) )
    passport_number = Field( Unicode( 20 ) )
    passport_expiry_date = Field( Date() )
    is_staff = Field( Boolean, default = False, index = True )
    is_superuser = Field( Boolean, default = False, index = True )
    picture = Field( camelot.types.Image( upload_to = 'person-pictures' ), deferred = True )
    comment = Field( camelot.types.RichText() )
    employers = OneToMany( 'EmployerEmployee', inverse = 'established_to', cascade='all, delete, delete-orphan' )

    @property
    def note(self):
        for person in self.__class__.query.filter_by(first_name=self.first_name, last_name=self.last_name):
            if person != self:
                return _('A person with the same name already exists')

    @property
    def name( self ):
        # we don't use full name in here, because for new objects, full name will be None, since
        # it needs to be fetched from the db first
        return u'%s %s' % ( self.first_name, self.last_name )

    def __unicode__( self ):
        return self.name or ''

Person = documented_entity()( Person )

class PartyRelationship( Entity ):
    using_options( tablename = 'party_relationship' )
    from_date = Field( Date(), default = datetime.date.today, required = True, index = True )
    thru_date = Field( Date(), default = end_of_times, required = True, index = True )
    comment = Field( camelot.types.RichText() )
    
    row_type = schema.Column( Unicode(40), nullable = False )
    __mapper_args__ = { 'polymorphic_on' : row_type }

    class Admin( EntityAdmin ):
        verbose_name = _('Relationship')
        verbose_name_plural = _('Relationships')
        list_display = ['from_date', 'thru_date']

class EmployerEmployee( PartyRelationship ):
    """Relation from employer to employee"""
    using_options( tablename = 'party_relationship_empl' )
    established_from = ManyToOne( Organization, required = True, ondelete = 'cascade', onupdate = 'cascade' )    # the employer
    established_to = ManyToOne( Person, required = True, ondelete = 'cascade', onupdate = 'cascade' )            # the employee
    partyrelationship_id = Field( Integer,
                                  ForeignKey('party_relationship.id'), 
                                  primary_key = True )

    __mapper_args__ = {'polymorphic_identity': 'employeremployee'}

    @ColumnProperty
    def first_name( self ):
        return sql.select( [Person.first_name], Person.party_id == self.established_to_party_id )

    @ColumnProperty
    def last_name( self ):
        return sql.select( [Person.last_name], Person.party_id == self.established_to_party_id )

    @ColumnProperty
    def social_security_number( self ):
        return sql.select( [Person.social_security_number], Person.party_id == self.established_to_party_id )

    def __unicode__( self ):
        return u'%s %s %s' % ( unicode( self.established_to ), _('Employed by'),unicode( self.established_from ) )

    class Admin( PartyRelationship.Admin ):
        verbose_name = _('Employment relation')
        verbose_name_plural = _('Employment relations')
        list_filter = ['established_from.name']
        list_search = ['established_from.name', 'established_to.first_name', 'established_to.last_name']

    class EmployeeAdmin( EntityAdmin ):
        verbose_name = _('Employee')
        list_display = ['established_to', 'from_date', 'thru_date']
        form_display = ['established_to', 'comment', 'from_date', 'thru_date']
        field_attributes = {'established_to':{'name':_( 'Name' )}}

    class EmployerAdmin( EntityAdmin ):
        verbose_name = _('Employer')
        list_display = ['established_from', 'from_date', 'thru_date']
        form_display = ['established_from', 'comment', 'from_date', 'thru_date']
        field_attributes = {'established_from':{'name':_( 'Name' )}}

class DirectedDirector( PartyRelationship ):
    """Relation from a directed organization to a director"""
    using_options( tablename = 'party_relationship_dir' )
    established_from = ManyToOne( Organization, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    established_to = ManyToOne( Party, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    title = Field( Unicode( 256 ) )
    represented_by = OneToMany( 'RepresentedRepresentor', inverse = 'established_to' )

    partyrelationship_id = Field( Integer,
                                  ForeignKey('party_relationship.id'), 
                                  primary_key = True )

    __mapper_args__ = {'polymorphic_identity': 'directeddirector'}

    class Admin( PartyRelationship.Admin ):
        verbose_name = _('Direction structure')
        verbose_name_plural = _('Direction structures')
        list_display = ['established_from', 'established_to', 'title', 'represented_by']
        list_search = ['established_from.full_name', 'established_to.full_name']
        field_attributes = {'established_from':{'name':_('Organization')},
                            'established_to':{'name':_('Director')}}

    class DirectorAdmin( Admin ):
        verbose_name = _('Director')
        list_display = ['established_to', 'title', 'from_date', 'thru_date']
        form_display = ['established_to', 'title', 'from_date', 'thru_date', 'represented_by', 'comment']

    class DirectedAdmin( Admin ):
        verbose_name = _('Directed organization')
        list_display = ['established_from', 'title', 'from_date', 'thru_date']
        form_display = ['established_from', 'title', 'from_date', 'thru_date', 'represented_by', 'comment']

class RepresentedRepresentor( Entity ):
    """Relation from a representing party to the person representing the party"""
    using_options( tablename = 'party_representor' )
    from_date = Field( Date(), default = datetime.date.today, required = True, index = True )
    thru_date = Field( Date(), default = end_of_times, required = True, index = True )
    comment = Field( camelot.types.RichText() )
    established_from = ManyToOne( Person, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    established_to = ManyToOne( DirectedDirector, required = True, ondelete = 'cascade', onupdate = 'cascade' )

    class Admin( EntityAdmin ):
        verbose_name = _('Represented by')
        list_display = ['established_from', 'from_date', 'thru_date']
        form_display = ['established_from', 'from_date', 'thru_date', 'comment']
        field_attributes = {'established_from':{'name':_( 'Name' )}}

class SupplierCustomer( PartyRelationship ):
    """Relation from supplier to customer"""
    using_options( tablename = 'party_relationship_suppl' )
    established_from = ManyToOne( Party, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    established_to = ManyToOne( Party, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    partyrelationship_id = Field( Integer,
                                  ForeignKey('party_relationship.id'), 
                                  primary_key = True )

    __mapper_args__ = {'polymorphic_identity': 'suppliercustomer'}

    class Admin( PartyRelationship.Admin ):
        verbose_name = _('Supplier - Customer')
        list_display = ['established_from', 'established_to', 'from_date', 'thru_date']

    class CustomerAdmin( EntityAdmin ):
        verbose_name = _('Customer')
        list_display = ['established_to', ]
        form_display = ['established_to', 'comment', 'from_date', 'thru_date']
        field_attributes = {'established_to':{'name':_( 'Name' )}}

    class SupplierAdmin( EntityAdmin ):
        verbose_name = _('Supplier')
        list_display = ['established_from', ]
        form_display = ['established_from', 'comment', 'from_date', 'thru_date']
        field_attributes = {'established_from':{'name':_( 'Name' )}}

class SharedShareholder( PartyRelationship ):
    """Relation from a shared organization to a shareholder"""
    using_options( tablename = 'party_relationship_shares' )
    established_from = ManyToOne( Organization, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    established_to = ManyToOne( Party, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    shares = Field( Integer() )
    partyrelationship_id = Field( Integer,
                                  ForeignKey('party_relationship.id'), 
                                  primary_key = True )

    __mapper_args__ = {'polymorphic_identity': 'sharedshareholder'}

    class Admin( PartyRelationship.Admin ):
        verbose_name = _('Shareholder structure')
        verbose_name_plural = _('Shareholder structures')
        list_display = ['established_from', 'established_to', 'shares',]
        list_search = ['established_from.full_name', 'established_to.full_name']
        field_attributes = {'established_from':{'name':_('Organization')},
                            'established_to':{'name':_('Shareholder')}}

    class ShareholderAdmin( Admin ):
        verbose_name = _('Shareholder')
        list_display = ['established_to', 'shares', 'from_date', 'thru_date']
        form_display = ['established_to', 'shares', 'from_date', 'thru_date', 'comment']
        form_size = (500, 300)

    class SharedAdmin( Admin ):
        verbose_name = _('Shares')
        verbose_name_plural = _('Shares')
        list_display = ['established_from', 'shares', 'from_date', 'thru_date']
        form_display = ['established_from', 'shares', 'from_date', 'thru_date', 'comment']
        form_size = (500, 300)

class PartyAddress( Entity ):
    using_options( tablename = 'party_address' )
    party = ManyToOne( Party, 
                       required = True, 
                       ondelete = 'cascade', 
                       onupdate = 'cascade',
                       lazy = 'subquery')
    address = ManyToOne( Address, 
                         required = True, 
                         ondelete = 'cascade', 
                         onupdate = 'cascade',
                         lazy = 'subquery' )
    from_date = Field( Date(), default = datetime.date.today, required = True, index = True )
    thru_date = Field( Date(), default = end_of_times, required = True, index = True )
    comment = Field( Unicode( 256 ) )

    def _get_address_field( self, name ):
        if self.address:
            return getattr( self.address, name )
        
    def _set_address_field( self, name, value ):
        if not self.address:
            self.address = Address()
        setattr( self.address, name, value )
        
    @hybrid.hybrid_property
    def street1( self ):
        return self._get_address_field( u'street1' )
    
    @street1.setter
    def street1_setter( self, value ):
        return self._set_address_field( u'street1', value )
    
    @street1.expression
    def street1_expression( self ):
        return Address.street1

    @hybrid.hybrid_property
    def street2( self ):
        return self._get_address_field( u'street2' )
    
    @street2.expression
    def street2_expression( self ):
        return Address.street2    
    
    @street2.setter
    def street2_setter( self, value ):
        return self._set_address_field( u'street2', value )    
    
    @hybrid.hybrid_property
    def city( self ):
        return self._get_address_field( u'city' )
    
    @city.setter
    def city_setter( self, value ):
        return self._set_address_field( u'city', value )

    def party_name( self ):
        return sql.select( [sql.func.coalesce(Party.full_name, '')],
                           whereclause = (Party.id==self.party_id))
    
    party_name = ColumnProperty( party_name, deferred = True )

    def __unicode__( self ):
        return '%s : %s' % ( unicode( self.party ), unicode( self.address ) )

    class Admin( EntityAdmin ):
        verbose_name = _('Address')
        verbose_name_plural = _('Addresses')
        list_search = ['party_name', 'street1', 'street2',]
        list_display = ['party_name', 'street1', 'street2', 'city', 'comment']
        form_display = [ 'party', 'street1', 'street2', 'city', 'comment', 
                         'from_date', 'thru_date']
        form_size = ( 700, 200 )
        field_attributes = dict(party_name=dict(editable=False, name='Party', minimal_column_width=30))
        
        def get_compounding_objects( self, party_address ):
            if party_address.address:
                yield party_address.address        

class AddressAdmin( PartyAddress.Admin ):
    """Admin with only the Address information and not the Party information"""
    verbose_name = _('Address')
    list_display = ['street1', 'city', 'comment']
    form_display = ['street1', 'street2', 'city', 'comment', 'from_date', 'thru_date']
    field_attributes = dict(street1 = dict(name=_('Street'),
                                           editable=True,
                                           nullable=False),
                            street2 = dict(name=_('Street Extra'),
                                           editable=True),
                            city = dict(name=_('City'),
                                        editable=True,
                                        nullable=False,
                                        delegate=delegates.Many2OneDelegate,
                                        target=City),
                            )
        
    def get_depending_objects( self, party_address ):
        if party_address.party:
            yield party_address.party

class PartyAddressRoleType( Entity ):
    using_options( tablename = 'party_address_role_type' )
    code = Field( Unicode( 10 ) )
    description = Field( Unicode( 40 ) )

    class Admin( EntityAdmin ):
        verbose_name = _('Address role type')
        list_display = ['code', 'description']

class ContactMechanism( Entity ):
    using_options( tablename = 'contact_mechanism' )
    mechanism = Field( camelot.types.VirtualAddress( 256 ), required = True )
    party_address = ManyToOne( PartyAddress, ondelete = 'set null', onupdate = 'cascade' )
    party_contact_mechanisms = OneToMany( 'PartyContactMechanism' )

    def __unicode__( self ):
        if self.mechanism:
            return u'%s : %s' % ( self.mechanism[0], self.mechanism[1] )

    class Admin( EntityAdmin ):
        form_size = ( 700, 150 )
        verbose_name = _('Contact mechanism')
        list_display = ['mechanism']
        form_display = Form( ['mechanism', 'party_address'] )
        field_attributes = {'mechanism':{'minimal_column_width':25}}

        def get_depending_objects(self, contact_mechanism ):
            for party_contact_mechanism in contact_mechanism.party_contact_mechanisms:
                yield party_contact_mechanism
                party = party_contact_mechanism.party
                if party:
                    yield party

ContactMechanism = documented_entity()( ContactMechanism )

class PartyContactMechanism( Entity ):
    using_options( tablename = 'party_contact_mechanism' )

    party = ManyToOne( Party, required = True, ondelete = 'cascade', onupdate = 'cascade' )
    contact_mechanism = ManyToOne( ContactMechanism, lazy='joined', required = True, ondelete = 'cascade', onupdate = 'cascade' )
    from_date = Field( Date(), default = datetime.date.today, required = True, index = True )
    thru_date = Field( Date(), default = end_of_times, index = True )
    comment = Field( Unicode( 256 ) )

    @hybrid.hybrid_property
    def mechanism( self ):
        if self.contact_mechanism != None:
            return self.contact_mechanism.mechanism    
       
    @mechanism.setter
    def mechanism_setter( self, value ):
        if value != None:
            if self.contact_mechanism:
                self.contact_mechanism.mechanism = value
            else:
                self.contact_mechanism = ContactMechanism( mechanism = value )
                
    @mechanism.expression 
    def mechanism_expression( self ):
        return ContactMechanism.mechanism

    def party_name( self ):
        return sql.select( [Party.full_name],
                           whereclause = (Party.id==self.party_id))
    
    party_name = ColumnProperty( party_name, deferred = True )

    def __unicode__( self ):
        return unicode( self.contact_mechanism )

    Admin = PartyContactMechanismAdmin

# begin category definition
class PartyCategory( Entity ):
    using_options( tablename = 'party_category' )
    name = Field( Unicode(40), index=True, required=True )
    color = Field( camelot.types.Color() )
# end category definition
    parties = ManyToMany( 'Party', lazy = True,
                          tablename='party_category_party', 
                          remote_colname='party_id',
                          local_colname='party_category_id')
                            
    def get_contact_mechanisms(self, virtual_address_type):
        """Function to be used to do messaging
        
        :param virtual_address_type: a virtual address type, such as 'phone' or 'email'
        :return: a generator that yields strings of contact mechanisms, egg 'info@example.com'
        """
        for party in self.parties:
            for party_contact_mechanism in party.contact_mechanisms:
                contact_mechanism = party_contact_mechanism.contact_mechanism
                if contact_mechanism:
                    virtual_address = contact_mechanism.mechanism
                    if virtual_address and virtual_address[0] == virtual_address_type:
                        yield virtual_address[1]
                
    def __unicode__(self):
        return self.name or ''
    
    class Admin( EntityAdmin ):
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        list_display = ['name', 'color']

#Phone = orm.aliased( ContactMechanism )
#Email = orm.aliased( ContactMechanism )
#Fax = orm.aliased( ContactMechanism )

class PartyAdmin( EntityAdmin ):
    verbose_name = _('Party')
    verbose_name_plural = _('Parties')
    list_display = ['name', 'email', 'phone'] # don't use full name, since it might be None for new objects
    list_search = ['full_name']
    list_filter = ['categories.name']
    form_display = ['addresses', 'contact_mechanisms', 'shares', 'directed_organizations']
    form_size = (700, 700)
    field_attributes = dict(addresses = {'admin':AddressAdmin},
                            contact_mechanisms = {'admin':PartyPartyContactMechanismAdmin},
                            suppliers = {'admin':SupplierCustomer.SupplierAdmin},
                            customers = {'admin':SupplierCustomer.CustomerAdmin},
                            employers = {'admin':EmployerEmployee.EmployerAdmin},
                            employees = {'admin':EmployerEmployee.EmployeeAdmin},
                            directed_organizations = {'admin':DirectedDirector.DirectedAdmin},
                            directors = {'admin':DirectedDirector.DirectorAdmin},
                            shares = {'admin':SharedShareholder.SharedAdmin},
                            shareholders = {'admin':SharedShareholder.ShareholderAdmin},
                            sex = dict( choices = [( u'M', _('male') ), ( u'F', _('female') )] ),
                            name = dict( minimal_column_width = 50 ),
                            street1 = dict( editable = True, 
                                            minimal_column_width = 50 ),
                            street2 = dict( editable = True, 
                                            minimal_column_width = 50 ),
                            city = dict( editable = True, 
                                         delegate = delegates.Many2OneDelegate,
                                         target = City ), 
                            email = dict( editable = True, 
                                          minimal_column_width = 20,
                                          address_type = 'email',
                                          from_string = lambda s:('email', s),
                                          delegate = delegates.VirtualAddressDelegate),
                            phone = dict( editable = True, 
                                          minimal_column_width = 20,
                                          address_type = 'phone',
                                          from_string = lambda s:('phone', s),
                                          delegate = delegates.VirtualAddressDelegate ),
                            fax = dict( editable = True, 
                                        minimal_column_width = 20,
                                        address_type = 'fax',
                                        from_string = lambda s:('fax', s),
                                        delegate = delegates.VirtualAddressDelegate ),                            

                            )

    def get_compounding_objects( self, party ):
        for party_contact_mechanism in party.contact_mechanisms:
            yield party_contact_mechanism
        for party_address in party.addresses:
            yield party_address
        
    #def flush(self, party):
        #from sqlalchemy.orm.session import Session
        #session = Session.object_session( party )
        #if session:
            ## 
            ## flush all contact mechanism related objects
            ##
            #objects = [party]
            #deleted = ( party in session.deleted )
            #for party_contact_mechanism in party.contact_mechanisms:
                #if deleted:
                    #session.delete( party_contact_mechanism )
                #objects.extend([ party_contact_mechanism, party_contact_mechanism.contact_mechanism ])
            #session.flush( objects )

Party.Admin = PartyAdmin

class OrganizationAdmin( Party.Admin ):
    verbose_name = _( 'Organization' )
    verbose_name_plural = _( 'Organizations' )
    list_display = ['name', 'tax_id', 'email', 'phone', 'fax']
    form_display = TabForm( [( _('Basic'), Form( [ 'name', 'email', 
                                                   'phone', 
                                                   'fax', 'tax_id', 
                                                   'street1',
                                                   'street2',
                                                   'city',
                                                   'addresses', 'contact_mechanisms'] ) ),
                            ( _('Employment'), Form( ['employees'] ) ),
                            ( _('Customers'), Form( ['customers'] ) ),
                            ( _('Suppliers'), Form( ['suppliers'] ) ),
                            ( _('Corporate'), Form( ['directors', 'shareholders', 'shares'] ) ),
                            ( _('Branding'), Form( ['logo'] ) ),
                            ( _('Category and Status'), Form( ['categories', 'status'] ) ),
                            ] )
    field_attributes = dict( Party.Admin.field_attributes )
    
    def get_query( self ):
        query = super( OrganizationAdmin, self ).get_query()
        query = query.options( orm.joinedload('contact_mechanisms') )
        return query

Organization.Admin = OrganizationAdmin

class PersonAdmin( Party.Admin ):
    verbose_name = _( 'Person' )
    verbose_name_plural = _( 'Persons' )
    list_display = ['first_name', 'last_name', 'email', 'phone']
    form_display = TabForm( [( _('Basic'), Form( [HBoxForm( [ Form( [WidgetOnlyForm('note'), 
                                                              'first_name', 
                                                              'last_name', 
                                                              'sex',
                                                              'email',
                                                              'phone',
                                                              'fax',
                                                              'street1',
                                                              'street2',
                                                              'city',] ),
                                                            [WidgetOnlyForm('picture'), ],
                                                     ] ),
                                                     'comment', ], scrollbars = False ) ),
                            ( _('Official'), Form( ['birthdate', 'social_security_number', 'passport_number',
                                                    'passport_expiry_date', 'addresses', 'contact_mechanisms',], scrollbars = False ) ),
                            ( _('Work'), Form( ['employers', 'directed_organizations', 'shares'], scrollbars = False ) ),
                            ( _('Category'), Form( ['categories',] ) ),
                            ] )
    field_attributes = dict( Party.Admin.field_attributes )
    field_attributes['note'] = {'delegate':delegates.NoteDelegate}
    
    def get_query( self ):
        query = super( PersonAdmin, self ).get_query()
        query = query.options( orm.joinedload('contact_mechanisms') )
        return query
    
Person.Admin = PersonAdmin

