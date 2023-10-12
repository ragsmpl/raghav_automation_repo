import pandas as pd
import boto3
import sys
import time
import requests
import os
import re

nested_dict = {}
ou_acc_info = {}
ou_id_final = ""
account_id_final = ""
file_path = 'alternateusers.csv'
# Read the CSV file using pandas
df = pd.read_csv(file_path, header=None)
def download_file():
    INSTANCE_URL = 'https://something.service-now.com'
    USERNAME = ''
    PASSWORD = ''
    
    DOWNLOAD_PATH = 'attachments' 
    # Set up headers for the request
    headers = {
        'Accept': 'application/json',
    }
    
    # Set up the API endpoint for the specific incident
    incident_endpoint = f'{INSTANCE_URL}/api/now/table/incident'
    incident_params = {
        'sysparm_query': f'number={"INC0010046"}',
        'sysparm_limit': 1,
    }
    
    auth = (USERNAME, PASSWORD)
    # Make the API request to retrieve the incident record
    incident_response = requests.get(incident_endpoint, auth=auth, params=incident_params)
    
    if incident_response.status_code == 200:
        incident_data = incident_response.json().get('result')[0]
    
        # Retrieve the sys_id of the incident
        incident_sys_id = incident_data.get('sys_id')
    
        # Construct the attachment endpoint URL
        attachment_endpoint = f'{INSTANCE_URL}/api/now/table/sys_attachment'
    
        # Define attachment query parameters
        attachment_params = {
            'sysparm_query': f'table_name=incident^table_sys_id={incident_sys_id}',
        }
    
        # Make the API request to retrieve attachments for the incident
        attachment_response = requests.get(attachment_endpoint, auth=auth, params=attachment_params)
    
        if attachment_response.status_code == 200:
            attachment_data = attachment_response.json().get('result')
            
            if attachment_data:
                attachment_sys_ids = [attachment.get('sys_id') for attachment in attachment_data]
                
                # Create the download directory if it doesn't exist
                if not os.path.exists(DOWNLOAD_PATH):
                    os.makedirs(DOWNLOAD_PATH)
    
                for sys_id in attachment_sys_ids:
                    attachment_url = f'{INSTANCE_URL}/api/now/attachment/{sys_id}/file'
                    response = requests.get(attachment_url, auth=auth)
                    
                    if response.status_code == 200:
                        content_disposition = response.headers.get('content-disposition')
                        print(content_disposition)
     
                        file_name_match = re.search(r'filename="([^"]+)"', content_disposition)
                        file_name = file_name_match.group(1)
                        
                        print("filename:"+file_name)
                        # Remove any potential URL encoding from the filename
                        file_name = requests.utils.unquote(file_name)
                        
                        file_path = os.path.join(DOWNLOAD_PATH, file_name)
                        
                        with open(file_path, 'wb') as file:
                            file.write(response.content)
                        
                        print(f'Saved attachment: {file_name}')
                    else:
                        print(f'Error downloading attachment with sys_id {sys_id}')
            else:
                print('No attachments found for the incident.')
        else:
            print('Failed to retrieve attachments:', attachment_response.status_code)
    
    else:
        print('Failed to retrieve incident:', incident_response.status_code)

def validate_account(desired_account_name, desired_ou_id):
    organizations_client = boto3.client('organizations')
    # Initialize the marker for pagination
    # Get the list of accounts within the desired OU
    response = organizations_client.list_accounts_for_parent(
        ParentId=desired_ou_id
    )

    # Initialize the marker for pagination
    marker = response.get('NextToken')

    # Store the accounts from the first search
    accounts = response['Accounts']

    # Continue the search until the matching account is found or all accounts are retrieved
    matching_account_id = None
    while not matching_account_id:
        # Iterate through the accounts and find the matching account name
        if not response['Accounts']:
            print("No account found")
            return("Not Found")
            break
        for account in accounts:
            if account['Name'] == desired_account_name:
                matching_account_id = account['Id']
                print(matching_account_id)
                return (matching_account_id)
                break
        print("maker" + str(marker))
        # Check if there are more accounts to retrieve with pagination
        if not marker:
            break

        # Get the next page of accounts using pagination
        response = organizations_client.list_accounts_for_parent(
            ParentId=desired_ou_id,
            NextToken=marker
        )

        # Update the marker for the next iteration
        marker = response.get('NextToken')

        # Add the accounts from the next page to the accounts list
        accounts.extend(response['Accounts'])
    return ("Not Found")


def validate_ou(desired_ou, ParentId):
    organizations_client = boto3.client('organizations')
    # desired_account_name = ""

    # desired_ou = "TestRaghav123"
    # Initialize the marker for pagination
    # Get the list of accounts within the desired OU
    response = organizations_client.list_organizational_units_for_parent(
        ParentId=ParentId,  # Replace with the actual ID of the parent OU.
    )
    # Store the accounts from the first search
    ous = response['OrganizationalUnits']
    matching_ou_id = None
    marker = response.get('NextToken')
    while not matching_ou_id:
        # Iterate through the accounts and find the matching account name
        if not response['OrganizationalUnits']:
            print("No OrganizationalUnits found")
            break
        for ou in ous:
            if ou['Name'] == desired_ou:
                matching_ou_id = ou['Id']
                return (matching_ou_id)
                break
        # Check if there are more accounts to retrieve with pagination
        if not marker:
            break

        # Get the next page of accounts using pagination
        response = organizations_client.list_organizational_units_for_parent(
            ParentId=ParentId,
            NextToken=marker
        )

        # Update the marker for the next iteration
        marker = response.get('NextToken')

        # Add the accounts from the next page to the accounts list
        ous.extend(response['OrganizationalUnits'])
    # Store the accounts from the first search
    return ("Not Found")


def add_user_to_permissionset(account_id, permission_set_name, user_email, ssoins_id, IdentityStoreId):
    identitystore_client = boto3.client('identitystore', region_name=region_name)
    response = identitystore_client.list_users(
        IdentityStoreId=IdentityStoreId,
        Filters=[
            {
                'AttributePath': 'UserName',
                'AttributeValue': user_email
            }
        ]
    )
    sso_client = boto3.client('sso-admin', region_name=region_name)
    PrincipalId = response['Users'][0]['UserId']
    instance_arn = f"arn:aws:sso:::instance/{ssoins_id}"
    permission_set_arns = []
    permission_set_arns_tmp = sso_client.list_permission_sets(InstanceArn=instance_arn)
    permission_set_arns.extend(permission_set_arns_tmp['PermissionSets'])
    while "NextToken" in permission_set_arns_tmp:
        permission_set_arns_tmp = sso_client.list_permission_sets(NextToken=permission_set_arns_tmp["NextToken"],
                                                                  InstanceArn=instance_arn)
        permission_set_arns.extend(permission_set_arns_tmp["PermissionSets"])
    for permission_set_arn in permission_set_arns:
        perpermission_set_name = sso_client.describe_permission_set(InstanceArn=instance_arn, PermissionSetArn=permission_set_arn)['PermissionSet']['Name']
        print(perpermission_set_name)
        print(permission_set_name)
        if perpermission_set_name == permission_set_name:
            response = sso_client.create_account_assignment(
                InstanceArn=f'arn:aws:sso:::instance/{ssoins_id}',
                TargetId=account_id,
                TargetType='AWS_ACCOUNT',
                PermissionSetArn=f'{permission_set_arn}',
                PrincipalType='USER',
                PrincipalId=PrincipalId
            )


def add_alternate_contact(AccountId, alternate_contact_type, email_address, name, phone_number, title):
    # Create a Boto3 client for AWS Account
    client = boto3.client('account')

    # Call the put_alternate_contact API
    response = client.put_alternate_contact(
        AccountId=AccountId,
        AlternateContactType=alternate_contact_type,
        EmailAddress=email_address,
        Name=name,
        PhoneNumber=phone_number,
        Title=title
    )

    # Print the response
    print(response)


def suspend_account():
    pass
    # This code is not working
    # Replace these variables with your own values
    # account_id_to_suspend = "797896970464"
    # response = client.close_account(
    # AccountId='797896970464'
    # )


def wait_for_provisioned_product_status(product_name):
    client = boto3.client('servicecatalog', region_name=region_name)
    for i in range(0, 30):
        time.sleep(60)
        try:
            output_values = client.get_provisioned_product_outputs(ProvisionedProductName=product_name)
            if output_values.get('Outputs') and output_values['Outputs']:
                account_number = output_values['Outputs'][0].get('OutputValue')
            else:
                account_number = None
        except Exception as e:
            print(str(e) + ", hence trying after 10 more seconds...")
            account_number = None

        if account_number:
            break

    return (account_number)


def add_account_under_ou(AccountName, AccountEmail, ManagedOrganizationalUnit, SSOUserEmail):

    ProvisionedProduct = "create_ctaccount_" + AccountName
    username, domain = SSOUserEmail.split('@')
    # Split the username based on the dot ('.')
    SSOUserFirstName, SSOUserLastName = username.split('.')

    client = boto3.client('servicecatalog', region_name=region_name)
    try:
        status = client.provision_product(

            ProductId=product_id,
            ProvisioningArtifactId=provisioning_artifact_id,
            ProvisionedProductName=ProvisionedProduct,
            ProvisioningParameters=[
                {
                    'Key': 'SSOUserEmail',
                    'Value': SSOUserEmail
                },
                {
                    'Key': 'SSOUserFirstName',
                    'Value': SSOUserFirstName
                },
                {
                    'Key': 'SSOUserLastName',
                    'Value': SSOUserLastName
                },
                {
                    'Key': 'ManagedOrganizationalUnit',
                    'Value': ManagedOrganizationalUnit
                },
                {
                    'Key': 'AccountName',
                    'Value': AccountName
                },
                {
                    'Key': 'AccountEmail',
                    'Value': AccountEmail
                },
            ]
        )
        print(status)  # Output the result of provision_product API call
        account_number =(wait_for_provisioned_product_status("create_ctaccount_" + AccountName))
        return account_number
    except Exception as e:
        print(f"There is an issue with the account creation. Look into the below error:\n{e}")
        exit(1)


def add_ou():
    # Replace these variables with your own values
    parent_id = "r-"
    ou_name = "TestRaghav123"

    # Create a boto3 client for AWS Organizations
    org_client = boto3.client('organizations')

    # Create the organizational unit
    response = org_client.create_organizational_unit(
        ParentId=parent_id,
        Name=ou_name
    )

    # Print the response to verify the creation of the OU
    print("Organizational Unit Created:")
    print("OU Id:", response['OrganizationalUnit']['Id'])
    print("OU Name:", response['OrganizationalUnit']['Name'])
    return (str(response['OrganizationalUnit']['Id']))


def delete_account():
    pass


def delete_user_from_permissionset(account_id, ):
    sso_client = boto3.client('sso-admin')
    response = sso_client.delete_account_assignment(
        InstanceArn=f'arn:aws:sso:::instance/{ssoins_id}',
        TargetId=account_id,
        TargetType='AWS_ACCOUNT',
        PermissionSetArn=f'arn:aws:sso:::permissionSet/{ssoins_id}/{permission_set_name}',
        PrincipalType='USER',
        PrincipalId=PrincipalId
    )


def check_user_in_sso(email):
    client = boto3.client('identitystore', region_name=region_name)
    try:
        # Call the list_users API to retrieve user details
        response = client.list_users(
            IdentityStoreId=IdentityStoreId,
            Filters=[
                {
                    'AttributePath': 'UserName',
                    'AttributeValue': email
                }
            ]
        )
        # Check if any users are returned
        users = response.get('Users', [])
        if len(users) > 0:
            print(f"The email '{email}' exists in the AWS SSO Identity Store.")
        else:
            print(f"The email '{email}' does not exist in the AWS SSO Identity Store.")
            sys.exit(0)
    except Exception as e:
        print("Error occurred while checking email existence:", str(e))



# Process the first 4 lines


def initial_check(file_path,provisioning_artifact_id,product_id,region_name,IdentityStoreId,ssoins_id,child_ou,ParentId,desired_ou_id):
    for index, row in df.head(5).iterrows():
        key = row[0]
        value = row[1]
        # Store key-value pair in ou_acc_info dictionary
        ou_acc_info[key] = value
    print("Printing Division Name: " + str(ou_acc_info['Division Name']))
    print("Printing Environment: " + str(ou_acc_info['Environment']))
    print("Printing Application Name: " + str(ou_acc_info['Application Name']))
    print("Printing Account Status: " + str(ou_acc_info['Account Status']))
    print("Printing OU Status: " + str(ou_acc_info['OU Status']))
    # Print the ou_acc_info dictionary
    if ou_acc_info['Environment'] == "dev" or ou_acc_info['Environment'] == "qa":
        child_ou = "Nonprod"
    else:
        child_ou = ou_acc_info['Environment']
    if ou_acc_info['OU Status'] == "New":
        add_ou()
        print("pass the OU id")
    else:
        print("check division OU")
        ou_id_final = validate_ou(str(ou_acc_info['Division Name']), desired_ou_id)
        if ou_id_final != "Not Found":
            print("Parent OU is found:" + ou_id_final)
            ou_id_final = validate_ou(child_ou, ou_id_final)
            print("Child OU is found:" + ou_id_final)
    
    if ou_acc_info['Account Status'] == "New":
        account_name = str(ou_acc_info['Application Name']) + "_" + str(ou_acc_info['Environment'])
        print(account_name)
        account_id_final = validate_account(account_name, ou_id_final)
        print("result of validate account:"+account_id_final)

        if str(account_id_final) == "Not Found":
            for index, row in df.iloc[6:].iterrows():
                name = row[0]
                title = row[1]
                email = row[2]
                phone = row[3]
                account_owner = row[4]
                operations_alerts = row[5]
                admin_access = row[6]
                read_only_access = row[7]
                billing_alerts = row[8]
                security_alerts = row[9]
                check_user_in_sso(email)
                nested_dict[name] = {
                    'title': title,
                    'email': email,
                    'phone': phone,
                    'account_owner': account_owner,
                    'operations_alerts': operations_alerts,
                    'admin_access': admin_access,
                    'read_only_access': read_only_access,
                    'billing_alerts': billing_alerts,
                    'security_alerts': security_alerts
                }
    
                print("processing user in account validate loop" + str(email))
                print(nested_dict[name])
                if name != "generic_email":
                    if nested_dict[name]['account_owner'] == "x":
                        print("create new account:" + account_name)
                        ACCEmail =  str(ou_acc_info['Division Name'])+"_"+str(ou_acc_info['Application Name'])+"_" + str(ou_acc_info['Environment'])+"@icfnext.com"
                        ou_variable =  str(ou_acc_info['Environment'])+" ("+str(ou_id_final)+")"
                        account_id_final = add_account_under_ou(account_name, ACCEmail, ou_variable, email)
                        if account_id_final == "None":
                            print("Issue in creating account")
                        else:
                            print("Account created:" + account_id_final)
                        break;
    
    
        else:
            print("account found:" + account_id_final)
        print("pass the account id:" + account_id_final)
    else:
        print("fetch account ID")
        print("pass the account id")
    account_processing(account_id_final, ssoins_id, IdentityStoreId, str(ou_acc_info['Division Name']))
    # Process the heading mentioned in the 5th line
    header_row = df.iloc[5]
    header = []
    for value in header_row:
        header.append(value)
    # Process the header as desired
    print("heading")
    print(header)


def account_processing(account_id_final, ssoins_id, IdentityStoreId,divname):
    for index, row in df.iloc[6:].iterrows():

        name = row[0]
        title = row[1]
        email = row[2]
        phone = row[3]
        account_owner = row[4]
        operations_alerts = row[5]
        admin_access = row[6]
        read_only_access = row[7]
        billing_alerts = row[8]
        security_alerts = row[9]
        check_user_in_sso(email)
        nested_dict[name] = {
            'title': title,
            'email': email,
            'phone': phone,
            'account_owner': account_owner,
            'operations_alerts': operations_alerts,
            'admin_access': admin_access,
            'read_only_access': read_only_access,
            'billing_alerts': billing_alerts,
            'security_alerts': security_alerts
        }
        print("account id final")
        print(account_id_final)
        print("processing user " + str(email))
        print(nested_dict[name])
        if name != "generic_email":
            if nested_dict[name]['account_owner'] == "x":
                print("adding div admin")
                permission_set_name = str(divname) + "_SSO_Administrator"
                print(permission_set_name)
                add_user_to_permissionset(account_id_final, permission_set_name, email, ssoins_id, IdentityStoreId)
            if nested_dict[name]['admin_access'] == "x":
                print("adding administrator")
                permission_set_name = str(divname) + "_SSO_Administrator"
                add_user_to_permissionset(account_id_final, permission_set_name, email, ssoins_id, IdentityStoreId)
            if nested_dict[name]['read_only_access'] == "x":
                print("adding readonly")
                permission_set_name = str(divname) + "_" + "ReadOnly"
                add_user_to_permissionset(account_id_final, permission_set_name, email, ssoins_id, IdentityStoreId)
        if nested_dict[name]['operations_alerts'] == "x":
            add_alternate_contact(account_id_final, "OPERATIONS", email, name, phone, title)
        if nested_dict[name]['billing_alerts'] == "x":
            add_alternate_contact(account_id_final, "BILLING", email, name, phone, title)
        if nested_dict[name]['security_alerts'] == "x":
            add_alternate_contact(account_id_final, "SECURITY", email, name, phone, title)
        # Process the values as desired
        print(name, title, email, phone, account_owner, operations_alerts, admin_access, read_only_access,
              billing_alerts, security_alerts)
        print(nested_dict)



if __name__ == "__main__":
    nested_dict = {}
    ou_acc_info = {}
    ou_id_final = ""
    account_id_final = ""

    file_path = 'attachments/alternateusers.csv'
    download_file()

    initial_check(file_path,provisioning_artifact_id,product_id,region_name,IdentityStoreId,ssoins_id,child_ou,ParentId,desired_ou_id)
    
