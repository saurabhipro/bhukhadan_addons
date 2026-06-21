# -*- coding: utf-8 -*-
"""IndusInd / corporate banking SOAP API helpers (GetAccBalance, ProcessTxnInXml, etc.)."""

import re
from xml.sax.saxutils import escape

SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
TEMPURI_NS = 'http://tempuri.org/'

# IndusInd UAT — IBL Domestic Payment Service v1
IBL_DOMESTIC_PAY_UAT_URL = (
    'https://indusapiuat.indusind.bank.in/indusapi-np/uat/domesticpayservice/v1'
)

OPERATION_PATHS = {
    'ProcessTxnInXml': 'processTxnInXml',
    'GetTxnResponseInXml': 'getTxnResponseInXml',
    'GetAccBalance': 'getAccBalance',
    'GetStatment': 'getStatement',
    'GetReturnTrxn': 'getReturnTrxn',
}


def resolve_service_url(base_url, method_name, append_operation=True):
    """Build per-operation URL for IBL domesticpayservice/v1 gateway."""
    base = (base_url or '').strip().rstrip('/')
    if not base:
        return base
    if not append_operation:
        return base
    segment = OPERATION_PATHS.get(method_name, method_name)
    if base.lower().endswith(f'/{segment.lower()}'):
        return base
    return f'{base}/{segment}'


def build_request_headers(method_name, client_id=None, client_secret=None, include_soap_action=True):
    """HTTP headers for IBL Domestic Payment Service (SOAP + IBL-Client-* auth)."""
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'Accept': 'text/xml, application/xml, */*',
    }
    if include_soap_action:
        headers['SOAPAction'] = soap_action_for_method(method_name)
    if client_id:
        headers['IBL-Client-Id'] = str(client_id).strip()
    if client_secret:
        headers['IBL-Client-Secret'] = str(client_secret).strip()
    return headers


def _soap_envelope(body_inner):
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}" xmlns:tem="{TEMPURI_NS}">'
        f'<soapenv:Header/><soapenv:Body>{body_inner}</soapenv:Body></soapenv:Envelope>'
    )


def _cdata_payload(tag, inner_xml):
    return f'<tem:{tag}><tem:strInput><![CDATA[{inner_xml}]]></tem:strInput></tem:{tag}>'


def build_get_acc_balance_envelope(customer_id, user_id, account_number):
    inner = (
        f'<CustomerBalEnq>'
        f'<CustomerID>{escape(str(customer_id or ""))}</CustomerID>'
        f'<UserID>{escape(str(user_id or ""))}</UserID>'
        f'<AccountNumber>{escape(str(account_number or ""))}</AccountNumber>'
        f'</CustomerBalEnq>'
    )
    return _soap_envelope(_cdata_payload('GetAccBalance', inner))


def build_process_txn_envelope(cust_id, txn_xml):
    return _soap_envelope(
        f'<tem:ProcessTxnInXml>'
        f'<tem:strCustId>{escape(str(cust_id or ""))}</tem:strCustId>'
        f'<tem:strInputTxn><![CDATA[{txn_xml}]]></tem:strInputTxn>'
        f'</tem:ProcessTxnInXml>'
    )


def build_payment_request_xml(values):
    """Build inner PaymentRequest XML for ProcessTxnInXml."""
    def _tag(name, val, allow_empty=False):
        text = '' if val is None else str(val)
        if not allow_empty and not text:
            return f'<{name}></{name}>'
        return f'<{name}>{escape(text)}</{name}>'

    txn = values
    return (
        f'<PaymentRequest><Transaction>'
        f'{_tag("TranType", txn.get("tran_type", "IMPS"))}'
        f'{_tag("CustomerRefNum", txn.get("customer_ref_num"))}'
        f'{_tag("DebitAccount", txn.get("debit_account"))}'
        f'{_tag("Amount", txn.get("amount"))}'
        f'{_tag("ValueDate", txn.get("value_date"))}'
        f'{_tag("BenName", txn.get("ben_name"))}'
        f'{_tag("BENE_ACNO", txn.get("bene_acno"))}'
        f'{_tag("BENE_IFSC_CODE", txn.get("bene_ifsc"))}'
        f'{_tag("BENE_BRANCH", txn.get("bene_branch", ""), True)}'
        f'{_tag("BENE_BANK", txn.get("bene_bank", ""), True)}'
        f'{_tag("Bene_MobileNo", txn.get("bene_mobile", ""), True)}'
        f'{_tag("Bene_EmailId", txn.get("bene_email", ""), True)}'
        f'{_tag("Bene_MMId", txn.get("bene_mmid", ""), True)}'
        f'{_tag("MakerId", txn.get("maker_id"))}'
        f'{_tag("CheckerId", txn.get("checker_id"))}'
        f'{_tag("Reserve1", txn.get("reserve1", ""), True)}'
        f'{_tag("Reserve2", txn.get("reserve2", ""), True)}'
        f'{_tag("Reserve3", txn.get("reserve3", ""), True)}'
        f'</Transaction></PaymentRequest>'
    )


def build_get_txn_response_envelope(customer_id, ibl_ref_no):
    inner = (
        f'<PaymentEnquiry>'
        f'<CustomerId>{escape(str(customer_id or ""))}</CustomerId>'
        f'<IBLRefNo>{escape(str(ibl_ref_no or ""))}</IBLRefNo>'
        f'</PaymentEnquiry>'
    )
    return _soap_envelope(_cdata_payload('GetTxnResponseInXml', inner))


def build_get_statement_envelope(customer_id, user_id, account_number, from_date, to_date):
    inner = (
        f'<CustomerStmtEnq>'
        f'<CustomerID>{escape(str(customer_id or ""))}</CustomerID>'
        f'<UserID>{escape(str(user_id or ""))}</UserID>'
        f'<AccountNumber>{escape(str(account_number or ""))}</AccountNumber>'
        f'<FromDate>{escape(str(from_date or ""))}</FromDate>'
        f'<ToDate>{escape(str(to_date or ""))}</ToDate>'
        f'</CustomerStmtEnq>'
    )
    # Bank WSDL uses GetStatment (typo in vendor API).
    return _soap_envelope(_cdata_payload('GetStatment', inner))


def build_get_return_trxn_envelope(customer_id):
    inner = (
        f'<ReturnEnquiry>'
        f'<CustomerID>{escape(str(customer_id or ""))}</CustomerID>'
        f'</ReturnEnquiry>'
    )
    return _soap_envelope(_cdata_payload('GetReturnTrxn', inner))


def extract_soap_result(response_text, result_tag):
    """Extract CDATA or plain text from SOAP result element."""
    if not response_text:
        return ''
    cdata_pattern = rf'<(?:\w+:)?{re.escape(result_tag)}[^>]*><!\[CDATA\[(.*?)\]\]></(?:\w+:)?{re.escape(result_tag)}>'
    match = re.search(cdata_pattern, response_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    plain_pattern = rf'<(?:\w+:)?{re.escape(result_tag)}[^>]*>(.*?)</(?:\w+:)?{re.escape(result_tag)}>'
    match = re.search(plain_pattern, response_text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        if text.startswith('<![CDATA[') and text.endswith(']]>'):
            return text[9:-3].strip()
        return text
    return response_text.strip()


def extract_xml_field(xml_text, field_name):
    if not xml_text:
        return ''
    match = re.search(rf'<{re.escape(field_name)}>(.*?)</{re.escape(field_name)}>', xml_text, re.DOTALL)
    return match.group(1).strip() if match else ''


def soap_action_for_method(method_name):
    return f'"http://tempuri.org/{method_name}"'
