# Marsh extension guide

Extensions are optional packages discovered through the standard Python packaging
entry-point mechanism.

Declare an entry point in your extension package:

    [project.entry-points."marsh.extensions"]
    my_extension = "my_package:plugin"

Declare the contract version in package metadata. The build backend must emit the
custom metadata field Marsh-Extension-Contract with value 1.

The extension entry point is only loaded after its contract metadata is compatible.

## Extension compatibility rules

1. Marsh-Extension-Contract must be present and equal to 1.
2. Extension package version is informational and must not be confused with the
   contract version.
3. Workflow IR version is a separate compatibility boundary.
4. Malformed metadata is reported without loading the extension.
